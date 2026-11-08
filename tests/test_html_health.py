"""T19: finding badges, the Health, Mud and Drift overlays, and the Health panel."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

pytest.importorskip("playwright")

from conftest import CASES, build, make_project

CONCEPTS = Path("docs/ontology/concepts")
MUDDY = """id: refund-window
name: Refund window
kind: attribute
status: defined
definition: >
  The number of days after delivery during which a buyer may ask for a refund.
relations:
  - {type: attribute_of, target: order}
open_questions: ["Does the window restart when an order is replaced?"]
"""


@pytest.fixture(scope="module")
def findings_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The multi-finding case plus a drift finding (W105), a proposed concept and an open question."""
    project = make_project(tmp_path_factory.mktemp("health"), "multi")
    shutil.copytree(CASES / "w105", project, dirs_exist_ok=True)
    (project / CONCEPTS / "refund-window.yaml").write_text(MUDDY, encoding="utf-8")
    (project / CONCEPTS / "lapsed.yaml").write_text(
        "id: lapsed\nname: Lapsed\nkind: entity\nstatus: proposed\ndefinition: ''\n"
        "relations: [{type: is_a, target: customer}]\nproposal: {rationale: seen in code}\n",
        encoding="utf-8",
    )
    manifest = project / "docs/ontology/ontology.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "  relation_types:\n",
            "  relation_types:\n    governs:\n      status: proposed\n      inverse: governed_by\n"
            "      proposal: {rationale: limits recur}\n",
        ),
        encoding="utf-8",
    )
    window = project / CONCEPTS / "refund-window.yaml"
    window.write_text(
        window.read_text(encoding="utf-8").replace(
            "  - {type: attribute_of, target: order}\n",
            "  - {type: attribute_of, target: order}\n  - {type: governs, target: customer}\n",
        ),
        encoding="utf-8",
    )
    return build(project)


def ids(page, selector: str) -> set[str]:
    return set(page.eval_on_selector_all(selector, "els => els.map(e => e.dataset.id)"))


def expected_findings(page) -> list[dict]:
    return page.evaluate("ontologyView.data.findings")


def test_badges_show_the_worst_severity(findings_page: Path, open_page) -> None:
    page = open_page(findings_page).page
    badges = dict(
        page.eval_on_selector_all(
            ".finding-badge", "els => els.map(e => [e.closest('.node').dataset.id, e.dataset.severity])"
        )
    )
    assert badges["promo-code"] == "error", "E004 outranks W101 and I204"
    assert badges["delivery-note"] == "warn"
    assert badges["order-placed-at"] == "warn"
    fill = page.evaluate("getComputedStyle(document.querySelector('.finding-badge circle')).fill")
    kind_fills = page.eval_on_selector_all(".glyph:not(.proposed)", "els => els.map(e => getComputedStyle(e).fill)")
    assert fill not in kind_fills, "severity colours are never kind colours"


def test_pane_lists_codes_and_criteria(findings_page: Path, open_page) -> None:
    page = open_page(findings_page).page
    page.locator(".node[data-id='promo-code']").click()
    codes = page.locator(".pane .finding .code").all_text_contents()
    assert codes == ["E004 · coherence", "W101 · clarity", "I204 · clarity"]


@pytest.mark.parametrize("overlay", ["health", "mud", "drift"])
def test_overlays_highlight_exactly_their_sets(findings_page: Path, open_page, overlay: str) -> None:
    page = open_page(findings_page).page
    page.locator(".overlay button", has_text=overlay.capitalize()).click()
    data = page.evaluate("ontologyView.data")
    nodes = {n for n in ids(page, ".node")}
    if overlay == "health":
        expected = {f["concept"] for f in data["findings"] if f["concept"] in nodes}
        edges: set[str] = set()
    elif overlay == "drift":
        expected = {f["concept"] for f in data["findings"] if f["code"] in ("W105", "W106")}
        edges = set()
    else:
        expected = {c["id"] for c in data["concepts"] if c["status"] == "proposed" or c["open_questions"]}
        edges = {e for e in ids(page, ".edge-group") if "|related_to|" in e or "|governs|" in e}
    assert ids(page, ".node.highlight") == expected
    assert ids(page, ".node.faded") == nodes - expected
    assert ids(page, ".edge-group.highlight") == edges
    if overlay == "mud":
        assert "lapsed" in expected and "refund-window" in expected
        assert any("|governs|" in e for e in edges) and any("|related_to|" in e for e in edges)
    assert page.evaluate("location.hash") == f"#?overlay={overlay}"


def test_health_panel_groups_by_criterion_and_focuses(findings_page: Path, open_page) -> None:
    page = open_page(findings_page).page
    total = len(expected_findings(page))
    tab = page.get_by_role("tab", name="Health")
    assert tab.locator(".count").text_content() == str(total)
    tab.click()
    groups = page.eval_on_selector_all(".health-panel .criterion", "els => els.map(e => e.dataset.criterion)")
    assert groups[:2] == ["clarity", "coherence"] and len(groups) == len(set(groups))
    assert page.locator(".health-panel li.finding").count() == total
    clarity = page.locator(".health-panel .criterion[data-criterion='clarity'] li").all()
    assert {li.get_attribute("data-code") for li in clarity} == {"W101", "I204"}
    page.locator(".health-panel .criterion[data-criterion='drift'] a.concept-link").first.click()
    assert page.get_by_role("tab", name="Graph").get_attribute("aria-selected") == "true"
    assert ids(page, ".node.selected") == {"order-placed-at"}


def test_sample_health_panel(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    page.get_by_role("tab", name="Health").click()
    assert page.locator(".health-panel li.finding").count() == 1
    assert page.locator(".health-panel li.finding").get_attribute("data-code") == "I204"
