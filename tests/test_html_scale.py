"""T22: the 300-concept fixture renders fast and reads as structure; themes and reduced motion."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("playwright")

from conftest import REPO, build, overlaps

sys.path.insert(0, str(REPO / "tests"))
from gen_large_fixture import CONCEPTS, RELATIONS, generate

FIRST_RENDER_MS = 2000
INTERACTION_MS = 150


@pytest.fixture(scope="module")
def large_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    project = tmp_path_factory.mktemp("large")
    generate(project)
    return build(project)


def test_generator_is_deterministic(tmp_path: Path) -> None:
    a = generate(tmp_path / "a")
    b = generate(tmp_path / "b")
    files = sorted(p.relative_to(a) for p in a.rglob("*.yaml"))
    assert len(files) == CONCEPTS + 1
    assert all((a / f).read_bytes() == (b / f).read_bytes() for f in files)


def test_large_fixture_renders_within_budget(large_page: Path, open_page) -> None:
    loaded = open_page(large_page)
    page = loaded.page
    assert loaded.errors == []
    assert page.locator(".node").count() == CONCEPTS
    assert page.locator("svg.graph line.edge").count() == RELATIONS
    elapsed = page.evaluate("performance.now()")  # time since navigation start, taken once the view is ready
    assert elapsed < FIRST_RENDER_MS, f"first render took {elapsed:.0f} ms"


def test_selection_and_zoom_stay_responsive(large_page: Path, open_page) -> None:
    page = open_page(large_page).page
    timings = page.evaluate(
        """() => {
          const time = (fn) => { const t0 = performance.now(); fn(); return performance.now() - t0; };
          const v = ontologyView;
          return {
            select: time(() => v.setState({selected: 'payment'})),
            hops: time(() => v.setState({hops: 3})),
            zoom: time(() => v.view.zoomBy(0.5)),
            clear: time(() => v.setState({selected: null, hops: 1})),
          };
        }"""
    )
    assert max(timings.values()) < INTERACTION_MS, timings


def test_large_graph_reads_as_clusters_not_a_hairball(large_page: Path, open_page) -> None:
    view = open_page(large_page)
    positions = view.positions()
    cluster = {i: i.split("-")[0] for i in positions}
    within, between = [], []
    ids = sorted(positions)
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            d = ((positions[a][0] - positions[b][0]) ** 2 + (positions[a][1] - positions[b][1]) ** 2) ** 0.5
            (within if cluster[a] == cluster[b] else between).append(d)
    ratio = (sum(between) / len(between)) / (sum(within) / len(within))
    assert ratio > 2.5, f"clusters are not separated: between/within distance ratio {ratio:.2f}"
    hubs = view.page.eval_on_selector_all(".node.hub", "els => els.length")
    assert hubs <= CONCEPTS * 0.15, "only real hubs keep their box when zoomed out"
    boxes = view.page.eval_on_selector_all(
        "svg.graph rect.box", "els => els.map(e => e.getBoundingClientRect().toJSON())"
    )
    assert overlaps([b for b in boxes if b["width"]]) == []


def test_selecting_while_zoomed_out_zooms_in_to_the_neighbourhood(large_page: Path, open_page) -> None:
    page = open_page(large_page).page
    assert float(page.locator("svg.graph").get_attribute("data-scale")) < 0.6
    page.evaluate("ontologyView.setState({selected: 'payment'})")
    scale = float(page.locator("svg.graph").get_attribute("data-scale"))
    assert 0.6 <= scale <= 1
    canvas = page.locator("svg.graph").bounding_box()
    for concept in page.eval_on_selector_all(".node.near", "els => els.map(e => e.dataset.id)"):
        box = page.locator(f".node[data-id='{concept}'] rect.box").bounding_box()
        assert canvas["x"] <= box["x"] and box["x"] + box["width"] <= canvas["x"] + canvas["width"]


# --- Themes and motion ----------------------------------------------------------------------


@pytest.mark.parametrize(("scheme", "expected"), [("light", "#ffffff"), ("dark", "#14171a")])
def test_theme_follows_prefers_color_scheme(sample_page: Path, browser, scheme: str, expected: str) -> None:
    context = browser.new_context(viewport={"width": 1280, "height": 720}, color_scheme=scheme, offline=True)
    page = context.new_page()
    page.goto(sample_page.as_uri())
    page.wait_for_function("window.ontologyView && window.ontologyView.ready")
    bg = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()")
    body = page.evaluate("getComputedStyle(document.body).backgroundColor")
    context.close()
    assert bg == expected
    r, g, b = (int(expected[i : i + 2], 16) for i in (1, 3, 5))
    assert body == f"rgb({r}, {g}, {b})"


def test_reduced_motion_sets_durations_to_zero(sample_page: Path, browser) -> None:
    context = browser.new_context(viewport={"width": 1280, "height": 720}, reduced_motion="reduce", offline=True)
    page = context.new_page()
    page.goto(sample_page.as_uri())
    page.wait_for_function("window.ontologyView && window.ontologyView.ready")
    token = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--duration-fast').trim()")
    node = page.evaluate("getComputedStyle(document.querySelector('.node')).transitionDuration")
    context.close()
    assert token == "0ms" and node == "0s"
