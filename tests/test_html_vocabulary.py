"""T20: the legend, the Vocabulary panel and extension-kind encodings."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("playwright")

from conftest import build, make_project, overlaps


def test_legend_is_always_visible_and_explains_on_hover(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    legend = page.get_by_role("complementary", name="Legend")
    assert legend.is_visible()
    assert legend.locator(".row[data-kind]").all_text_contents() == ["entity", "event", "attribute", "metric"]
    tip = page.locator(".legend-tip")
    assert not tip.is_visible()
    legend.locator(".row[data-kind='metric']").hover()
    assert tip.is_visible()
    assert "aggregating over many instances" in tip.text_content()
    legend.locator(".type[data-type='part_of']").hover()
    assert "component" in tip.text_content()
    legend.locator(".badge-item[data-severity='warn']").hover()
    assert tip.text_content().startswith("warning")
    page.locator(".node[data-id='customer']").click()  # still there with a selection, and on other tabs' return
    assert legend.is_visible()


def test_legend_entries_are_reachable_by_keyboard(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    page.locator(".legend .row[data-status='proposed']").focus()
    assert page.locator(".legend-tip").is_visible()
    assert "Needs a definition" in page.locator(".legend-tip").text_content()


def test_fit_keeps_the_graph_clear_of_the_legend(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    legend = page.locator(".legend").bounding_box()
    boxes = page.eval_on_selector_all("svg.graph rect.box", "els => els.map(e => e.getBoundingClientRect().toJSON())")
    under_legend = [j for i, j in overlaps([legend, *boxes]) if i == 0]
    assert under_legend == [], "no concept box sits under the legend after fit-to-view"


def test_vocabulary_panel_lists_core_and_extensions(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    page.get_by_role("tab", name="Vocabulary").click()
    panel = page.locator(".vocab-panel")
    kinds = panel.locator(".vocab-section", has_text="Kinds").locator("tbody tr")
    assert kinds.count() == 4
    entity = panel.locator("tr[data-id='entity']")
    cells = entity.locator("td").all_text_contents()
    assert cells[0] == "core" and int(cells[1]) > 0 and "identity of its own" in cells[2]
    types = panel.locator(".vocab-section", has_text="Relation types")
    measures = types.locator("tr[data-id='measures']").locator("td").all_text_contents()
    assert measures[0] == "defined" and measures[2] == "metric → entity, event"
    derived = types.locator("tr[data-id='derived_from']").locator("td").all_text_contents()
    assert derived[0] == "proposed" and derived[3] == "Needs a definition"
    assert "inverse: measured by" in types.locator("tr[data-id='measures'] th").text_content()


def test_clicking_a_vocabulary_entry_filters_the_graph(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    page.get_by_role("tab", name="Vocabulary").click()
    page.locator(".vocab-panel tr[data-id='metric'] button").click()
    assert page.get_by_role("tab", name="Graph").get_attribute("aria-selected") == "true"
    visible = page.eval_on_selector_all(".node:not(.hidden)", "els => els.map(e => e.dataset.id)")
    kinds = page.evaluate("Object.fromEntries(ontologyView.data.concepts.map(c => [c.id, c.kind]))")
    assert visible and {kinds[v] for v in visible} == {"metric"}
    page.get_by_role("tab", name="Vocabulary").click()
    page.locator(".vocab-panel tr[data-id='is_a'] button").click()
    shown = page.eval_on_selector_all(".edge-group:not(.hidden)", "els => els.map(e => e.dataset.id)")
    assert shown and all("|is_a|" in e for e in shown)


def test_ninth_kind_uses_the_neutral_fallback(tmp_path: Path, open_page) -> None:
    project = make_project(tmp_path, "w113")  # five extension kinds in use: nine in all
    manifest = project / "docs/ontology/ontology.yaml"
    assert "promo:" in manifest.read_text(encoding="utf-8")
    page = open_page(build(project)).page
    slots = dict(
        page.eval_on_selector_all(
            ".node .glyph", "els => els.map(e => [e.closest('.node').dataset.id, e.getAttribute('class')])"
        )
    )
    # Extensions by sorted id: channel, promo, region_kind, season -> slots 5-8; tier -> fallback.
    assert "k5" in slots["channel-thing"] and "k8" in slots["season-thing"]
    assert "k-fallback" in slots["tier-thing"]
    legend_kinds = page.locator(".legend .row[data-kind]").all_text_contents()
    assert legend_kinds[-1] == "tier"
