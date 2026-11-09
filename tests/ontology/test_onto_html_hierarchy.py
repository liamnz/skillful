"""T21: the hierarchy layout and semantic zoom."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("playwright")

from ontotest import overlaps


def hierarchy(page) -> None:
    page.locator(".layout button", has_text="Hierarchy").click()


def acyclic_edges(page) -> list[tuple[str, str]]:
    return [
        tuple(e)
        for e in page.evaluate(
            """() => { const v = ontologyView;
                 return v.model.edges.filter(e => (v.model.relationTypes.get(e.type) || {}).acyclic)
                                     .map(e => [e.source, e.target]); }"""
        )
    ]


def test_hierarchy_puts_parents_above_children(sample_page: Path, open_page) -> None:
    view = open_page(sample_page)
    hierarchy(view.page)
    positions = view.positions()
    edges = acyclic_edges(view.page)
    assert edges, "the sample has is_a, part_of and derived_from relations"
    for child, parent in edges:
        assert positions[parent][1] < positions[child][1], f"{parent} sits above {child}"
    rows = {y for _, y in positions.values()}
    assert len(rows) <= 5, "concepts sit on a few level rows"
    boxes = view.page.eval_on_selector_all(
        "svg.graph rect.box", "els => els.map(e => e.getBoundingClientRect().toJSON())"
    )
    assert overlaps(boxes) == []
    assert view.page.evaluate("location.hash") == "#?layout=hierarchy"


def test_hierarchy_is_deterministic_and_deep_linkable(sample_page: Path, open_page) -> None:
    first = open_page(sample_page, hash="#?layout=hierarchy")
    second = open_page(sample_page)
    hierarchy(second.page)
    assert first.page.locator(".layout button[aria-pressed='true']").text_content() == "Hierarchy"
    assert first.positions() == second.positions()


def test_switching_back_restores_the_force_layout(sample_page: Path, open_page) -> None:
    view = open_page(sample_page)
    force = view.positions()
    hierarchy(view.page)
    assert view.positions() != force
    view.page.locator(".layout button", has_text="Force").click()
    assert view.positions() == force


def test_depth_levels_on_a_dag_with_a_diamond(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    depth = page.evaluate(
        """() => {
          const ids = ['d', 'b', 'c', 'g', 'a', 'x', 'p', 'q'];
          const nodes = ids.map(id => ({id}));
          const edges = [
            ['b', 'is_a', 'd'], ['c', 'is_a', 'd'],          // the diamond's two sides
            ['g', 'part_of', 'b'],                           // a longer path down one side
            ['a', 'is_a', 'g'], ['a', 'is_a', 'c'],          // several parents: below the deepest
            ['x', 'attribute_of', 'a'],                      // no hierarchy: hangs below 'a'
            ['p', 'related_to', 'q'],                        // a group with no hierarchy at all
          ].map(([source, type, target]) => ({source, type, target}));
          const relationTypes = new Map(['is_a', 'part_of', 'attribute_of', 'related_to']
            .map(id => [id, {id, acyclic: id === 'is_a' || id === 'part_of'}]));
          const levels = OntologyGraph.depthLevels({nodes, edges, relationTypes});
          return Object.fromEntries(levels.depth);
        }"""
    )
    assert depth == {"d": 0, "b": 1, "c": 1, "g": 2, "a": 3, "x": 4, "p": 0, "q": 1}


def test_zoomed_out_concepts_collapse_to_glyphs_except_hubs_and_focus(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    page.locator(".node[data-id='product']").click()
    for _ in range(4):
        page.get_by_role("button", name="Zoom out").click()
    assert "zoomed-out" in page.locator("svg.graph").get_attribute("class")
    shown = page.eval_on_selector_all(
        ".node",
        "els => els.filter(e => getComputedStyle(e.querySelector('.box')).display !== 'none').map(e => e.dataset.id)",
    )
    hubs = set(page.eval_on_selector_all(".node.hub", "els => els.map(e => e.dataset.id)"))
    near = set(page.eval_on_selector_all(".node.near", "els => els.map(e => e.dataset.id)"))
    assert hubs and set(shown) == hubs | near | {"product"}
    solo = page.locator(".node[data-id='plan-price'] .glyph-solo")
    assert solo.evaluate("e => getComputedStyle(e).display") != "none"


def test_zoomed_in_every_edge_is_labelled(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    for _ in range(4):
        page.get_by_role("button", name="Zoom in").click()
    assert "zoomed-in" in page.locator("svg.graph").get_attribute("class")
    hidden = page.eval_on_selector_all(
        ".edge-label", "els => els.filter(e => getComputedStyle(e).visibility !== 'visible').length"
    )
    assert hidden == 0
