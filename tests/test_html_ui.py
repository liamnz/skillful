"""T9: the graph renders deterministically from file://, offline, with every encoding.

Dev only. Needs pytest-playwright and Playwright's Chromium:
    uv run --with pytest --with pytest-playwright --with pyyaml --with jsonschema pytest tests/test_html_ui.py -q
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

pytest.importorskip("playwright")

from conftest import REPO, make_project, run_onto
from playwright.sync_api import Browser, Page

SAMPLE = REPO / "examples" / "sample-project"
OUTPUT = Path("docs/ontology/index.html")
VIEWPORT = {"width": 1280, "height": 720}  # the minimum supported viewport


def build(project: Path) -> Path:
    result = run_onto(["build"], cwd=project)
    assert result.returncode == 0, result.stderr
    return project / OUTPUT


@pytest.fixture(scope="module")
def sample_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    project = tmp_path_factory.mktemp("ui") / "sample"
    shutil.copytree(SAMPLE, project, ignore=shutil.ignore_patterns("index.html"))
    return build(project)


class Loaded:
    """A page opened from file:// with every non-file request blocked and recorded."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.errors: list[str] = []
        self.requests: list[str] = []
        page.on("console", lambda msg: msg.type == "error" and self.errors.append(msg.text))
        page.on("pageerror", lambda exc: self.errors.append(str(exc)))

        def route(r) -> None:
            if r.request.url.startswith("file:"):
                r.continue_()
            else:
                self.requests.append(r.request.url)
                r.abort()

        page.route("**/*", route)

    def positions(self) -> dict[str, list[float]]:
        return self.page.evaluate("window.ontologyView.positions()")


@pytest.fixture
def open_page(browser: Browser) -> Iterator[Callable[..., Loaded]]:
    contexts = []

    def opener(path: Path, viewport: dict[str, int] = VIEWPORT) -> Loaded:
        context = browser.new_context(viewport=viewport, offline=True)
        contexts.append(context)
        loaded = Loaded(context.new_page())
        loaded.page.goto(path.as_uri())
        loaded.page.wait_for_function("window.ontologyView && window.ontologyView.ready")
        return loaded

    yield opener
    for context in contexts:
        context.close()


def overlaps(boxes: list[dict[str, float]]) -> list[tuple[int, int]]:
    """Pairs of rectangles ({x, y, width, height}, top-left origin) that overlap."""
    found = []
    for i, a in enumerate(boxes):
        for j in range(i + 1, len(boxes)):
            b = boxes[j]
            if (
                a["x"] < b["x"] + b["width"]
                and b["x"] < a["x"] + a["width"]
                and a["y"] < b["y"] + b["height"]
                and b["y"] < a["y"] + a["height"]
            ):
                found.append((i, j))
    return found


# --- Loading ----------------------------------------------------------------------


def test_loads_offline_from_file_with_no_errors(sample_page: Path, open_page) -> None:
    view = open_page(sample_page)
    assert view.page.url.startswith("file:")
    assert view.errors == []
    assert view.requests == [], "the page requested nothing from the network"
    assert view.page.evaluate("window.ontologyView.d3Loaded")


# --- Structure and encodings ------------------------------------------------------


def test_one_box_per_concept_and_one_edge_per_relation(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    assert page.locator("svg.graph .node").count() == 22
    assert page.locator("svg.graph .edge").count() == 21
    assert page.locator(".node[data-id='customer'] .label").text_content() == "Customer"
    assert page.locator(".node[data-id='customer'] rect.box").count() == 1


def test_boxes_never_overlap_and_sit_inside_the_canvas(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    rects = page.evaluate(
        "[...document.querySelectorAll('svg.graph rect.box')].map(r => r.getBoundingClientRect().toJSON())"
    )
    assert len(rects) == 22
    assert overlaps(rects) == []
    canvas = page.evaluate("document.querySelector('svg.graph').getBoundingClientRect().toJSON()")
    for r in rects:
        assert canvas["left"] <= r["left"] and r["right"] <= canvas["right"]
        assert canvas["top"] <= r["top"] and r["bottom"] <= canvas["bottom"]


def test_core_kinds_use_fixed_slots_and_shapes(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    expected = {
        "customer": ("1", "circle"),
        "order-placed": ("2", "diamond"),
        "customer-region": ("3", "square"),
        "retention-rate": ("4", "triangle"),
    }
    for concept, (slot, shape) in expected.items():
        glyph = page.locator(f".node[data-id='{concept}'] .glyph")
        assert glyph.get_attribute("data-shape") == shape
        assert f"k{slot}" in glyph.get_attribute("class").split()
        assert glyph.get_attribute("d")


def test_status_is_shown_by_the_box_outline(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    style = "(sel) => { const s = getComputedStyle(document.querySelector(sel)); return [s.strokeDasharray]; }"
    defined = page.evaluate(style, ".node[data-id='customer'] rect.box")
    proposed = page.evaluate(style, ".node[data-id='churned-account'] rect.box")
    assert defined[0] == "none" and proposed[0] != "none"
    assert "proposed" in page.locator(".node[data-id='churned-account'] .glyph").get_attribute("class")
    deprecated = page.evaluate("getComputedStyle(document.querySelector(\".node[data-id='client-account']\")).opacity")
    assert float(deprecated) < 1


def test_relation_line_styles(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page

    def edge(source: str, type_: str, target: str) -> dict:
        return page.evaluate(
            """(id) => { const e = document.querySelector(`.edge[data-id="${id}"]`);
                 return {marker: e.getAttribute('marker-end'), dash: getComputedStyle(e).strokeDasharray}; }""",
            f"{source}|{type_}|{target}",
        )

    is_a = edge("active-customer", "is_a", "customer")
    has = edge("customer", "has", "order")
    related = edge("subscription", "related_to", "subscription-plan")
    assert "hollow" in is_a["marker"] and is_a["dash"] == "none"
    assert "filled" in has["marker"] and has["dash"] == "none"
    assert related["marker"] is None and related["dash"] != "none"


def test_edge_labels_appear_on_hover_with_cardinality(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    label = page.locator(".edge-label[data-id='customer|has|order']")
    assert label.text_content() == "has · 1:N"
    assert not label.is_visible(), "labels are hidden at rest until T15's focus labels them"
    assert page.locator(".edge-label[data-id='active-customer|is_a|customer']").text_content() == "is a"
    page.locator(".edge-hit[data-id='customer|has|order']").hover(force=True)
    assert label.is_visible()
    halo = page.evaluate("getComputedStyle(document.querySelector('.edge-label')).paintOrder")
    assert halo.startswith("stroke"), "the label's halo is painted beneath its text"


def test_extension_kinds_get_their_shapes(tmp_path: Path, open_page) -> None:
    project = make_project(tmp_path)
    ontology = project / "docs/ontology"
    names = ("alpha", "beta", "gamma", "delta")  # sorted: alpha, beta, delta, gamma
    entry = '      status: proposed\n      definition: ""\n      proposal: {rationale: "test"}\n'
    kinds = "".join(f"    {k}:\n{entry}" for k in names)
    manifest = ontology / "ontology.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("extensions:\n", "extensions:\n  kinds:\n" + kinds, 1),
        encoding="utf-8",
    )
    for kind in names:
        (ontology / "concepts" / f"thing-{kind}.yaml").write_text(
            f"id: thing-{kind}\nname: Thing {kind}\nkind: {kind}\nstatus: proposed\nproposal: {{rationale: test}}\n",
            encoding="utf-8",
        )
    page = open_page(build(project)).page
    expected = {"alpha": ("5", "cross"), "beta": ("6", "star"), "delta": ("7", "wye"), "gamma": ("8", "hexagon")}
    for kind, (slot, shape) in expected.items():
        glyph = page.locator(f".node[data-id='thing-{kind}'] .glyph")
        assert glyph.get_attribute("data-shape") == shape
        assert f"k{slot}" in glyph.get_attribute("class").split()
        assert glyph.get_attribute("d"), f"{shape} has a path"


# --- Determinism ------------------------------------------------------------------


def test_two_loads_give_identical_positions(sample_page: Path, open_page) -> None:
    first = open_page(sample_page).positions()
    second = open_page(sample_page).positions()
    assert len(first) == 22
    assert first == second


def test_layout_does_not_depend_on_the_viewport(sample_page: Path, open_page) -> None:
    small = open_page(sample_page).positions()
    large = open_page(sample_page, {"width": 1920, "height": 1080}).positions()
    assert small == large


def test_there_is_no_animated_settling(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    snapshot = "[...document.querySelectorAll('svg.graph .node')].map(n => n.getAttribute('transform'))"
    at_load = page.evaluate(snapshot)
    page.wait_for_timeout(500)
    assert page.evaluate(snapshot) == at_load


# --- Pure geometry (graph-model.js) -----------------------------------------------


def test_separate_removes_every_overlap(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    boxes = page.evaluate(
        """() => {
          const nodes = [];
          for (let i = 0; i < 40; i++) nodes.push({id: 'n' + i, x: (i % 5) * 3, y: (i % 3) * 2, w: 80 + i, h: 24});
          OntologyGraph.separate(nodes, 8);
          return nodes.map(n => ({x: n.x - n.w / 2, y: n.y - n.h / 2, width: n.w, height: n.h}));
        }"""
    )
    assert overlaps(boxes) == []


def test_seed_positions_come_from_ids(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    same = page.evaluate("JSON.stringify(OntologyGraph.seedPosition('customer', 100))")
    assert same == page.evaluate("JSON.stringify(OntologyGraph.seedPosition('customer', 100))")
    assert same != page.evaluate("JSON.stringify(OntologyGraph.seedPosition('order', 100))")
