"""T18: filters and the list view."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("playwright")


def ids(page, selector: str) -> list[str]:
    return page.eval_on_selector_all(selector, "els => els.map(e => e.dataset.id)")


def open_filters(page) -> None:
    if page.locator(".filters-panel").is_hidden():
        page.locator(".filters-button").click()


def toggle(page, group: str, value: str) -> None:
    open_filters(page)
    page.locator(f".filters-panel input[data-group='{group}'][value='{value}']").click()


def kinds(page) -> dict[str, str]:
    return page.evaluate("Object.fromEntries(ontologyView.data.concepts.map(c => [c.id, c.kind]))")


def test_kind_filter_hides_concepts_in_graph_and_list(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    toggle(page, "kinds", "metric")
    metrics = {i for i, k in kinds(page).items() if k == "metric"}
    assert set(ids(page, ".node.hidden")) == metrics
    assert page.locator(".filters-button").text_content() == "Filters · 1"
    page.get_by_role("tab", name="List").click()
    listed = ids(page, ".concept-table tbody tr")
    assert set(listed) == set(kinds(page)) - metrics
    assert "(filtered)" in page.locator(".concept-table caption").text_content()


def test_edges_to_hidden_concepts_are_stubs(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    toggle(page, "kinds", "metric")
    stubs = ids(page, ".edge-group.stub")
    assert stubs and all(any(part in stubs_id for part in ("measures", "derived_from")) for stubs_id in stubs)
    length = page.evaluate(
        """id => { const l = document.querySelector(`.edge-group[data-id="${id}"] line.edge`);
                   const v = (name) => l[name].baseVal.value;
                   return Math.hypot(v('x2') - v('x1'), v('y2') - v('y1')); }""",
        "retention-rate|measures|customer",
    )
    stub = page.evaluate(
        "parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--edge-stub-length'))"
    )
    assert length == pytest.approx(stub, abs=0.5)
    edges_between_hidden = ids(page, ".edge-group.hidden")
    assert "net-revenue|derived_from|gross-revenue" in edges_between_hidden


def test_status_and_relation_type_filters(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    toggle(page, "statuses", "deprecated")
    assert ids(page, ".node.hidden") == ["client-account"]
    toggle(page, "types", "is_a")
    hidden_edges = ids(page, ".edge-group.hidden")
    assert hidden_edges and all("|is_a|" in e for e in hidden_edges)
    page.get_by_role("button", name="Show all").click()
    assert ids(page, ".node.hidden") == [] and ids(page, ".edge-group.hidden") == []


def test_filtering_out_the_selection_clears_it(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    page.locator(".node[data-id='retention-rate']").click()
    toggle(page, "kinds", "metric")
    assert ids(page, ".node.selected") == []


def test_list_sorts_by_each_column(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    page.get_by_role("tab", name="List").click()
    names = page.locator(".concept-table tbody th").all_text_contents()
    assert [n.strip() for n in names] == sorted((n.strip() for n in names), key=str.lower)
    header = page.locator(".concept-table th", has_text="Relations")
    header.locator("button").click()
    assert header.get_attribute("aria-sort") == "ascending"
    header.locator("button").click()
    assert header.get_attribute("aria-sort") == "descending"
    counts = [int(c) for c in page.locator(".concept-table tbody td:nth-child(4)").all_text_contents()]
    assert counts == sorted(counts, reverse=True)


def test_list_selection_is_shared_with_graph_and_pane(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    page.get_by_role("tab", name="List").click()
    page.locator(".concept-table tbody tr[data-id='order'] td").first.click()
    assert page.locator(".concept-table tbody tr[data-id='order']").get_attribute("aria-selected") == "true"
    assert page.locator(".pane h2").text_content() == "Order"
    page.get_by_role("tab", name="Graph").click()
    assert ids(page, ".node.selected") == ["order"]


def test_accessibility_smoke(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    assert page.get_by_role("tablist", name="Views").is_visible()
    assert page.get_by_role("tab", name="Graph").get_attribute("aria-selected") == "true"
    assert page.get_by_role("combobox", name="Search concepts and terms").count() == 1
    assert page.get_by_role("group", name="Hops").count() == 1
    labels = page.eval_on_selector_all(".node", "els => els.map(e => e.getAttribute('aria-label'))")
    assert all(label and "(" in label for label in labels), "every concept in the graph has a name, kind and status"
    page.get_by_role("tab", name="List").click()
    table = page.get_by_role("table")
    assert table.locator("caption").count() == 1
    assert table.get_by_role("columnheader").count() == 6
    assert table.get_by_role("rowheader").count() == 22, "each row is headed by the concept's name"
    page.locator(".concept-table tbody tr[data-id='customer'] td").first.click()
    pane = page.get_by_role("complementary", name="Customer")
    assert pane.is_visible()
    assert pane.get_by_role("heading", level=3).count() >= 5
    for button in page.locator("button").all():
        if button.is_visible():
            assert (button.text_content() or "").strip() or button.get_attribute("aria-label")


def test_only_shows_a_single_value(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    open_filters(page)
    page.locator(".filters-panel .filter-row:has(input[value='has'])").hover()
    page.get_by_role("button", name="Show only has").click()
    shown = ids(page, ".edge-group:not(.hidden)")
    assert shown and all("|has|" in e for e in shown)
    checked = page.eval_on_selector_all(
        ".filters-panel input[data-group='types']:checked", "els => els.map(e => e.value)"
    )
    assert checked == ["has"]


def test_none_then_pick_a_few(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    open_filters(page)
    page.get_by_role("button", name="Hide every kind").click()
    assert len(ids(page, ".node.hidden")) == len(kinds(page))
    toggle(page, "kinds", "event")
    toggle(page, "kinds", "metric")
    visible = set(kinds(page)) - set(ids(page, ".node.hidden"))
    assert {kinds(page)[v] for v in visible} == {"event", "metric"}
    page.get_by_role("button", name="Show every kind").click()
    assert ids(page, ".node.hidden") == []
