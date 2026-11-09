"""T15: selection, neighbourhood focus, hover preview and the detail pane."""

from __future__ import annotations

from collections import deque
from pathlib import Path

import pytest

pytest.importorskip("playwright")

import yaml
from ontotest import SAMPLE

CONCEPTS = SAMPLE / "docs" / "ontology" / "concepts"


def sample_neighbourhood(concept: str, hops: int) -> set[str]:
    """The expected N-hop neighbourhood, computed from the YAML records (either direction)."""
    adjacency: dict[str, set[str]] = {}
    records = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in CONCEPTS.glob("*.yaml")]
    ids = {r["id"] for r in records}
    for r in records:
        adjacency.setdefault(r["id"], set())
        for rel in r.get("relations") or []:
            if rel["target"] in ids and rel["target"] != r["id"]:
                adjacency[r["id"]].add(rel["target"])
                adjacency.setdefault(rel["target"], set()).add(r["id"])
    seen = {concept: 0}
    queue = deque([concept])
    while queue:
        node = queue.popleft()
        if seen[node] == hops:
            continue
        for other in adjacency[node]:
            if other not in seen:
                seen[other] = seen[node] + 1
                queue.append(other)
    return set(seen)


def classes(page, selector: str) -> list[str]:
    return page.eval_on_selector_all(selector, "els => els.map(e => e.dataset.id)")


def select(page, concept: str) -> None:
    page.locator(f".node[data-id='{concept}']").click()


@pytest.mark.parametrize("hops", [1, 2, 3])
def test_selection_highlights_exactly_the_neighbourhood(sample_page: Path, open_page, hops: int) -> None:
    page = open_page(sample_page).page
    select(page, "customer")
    if hops != 1:
        page.locator(".hops button", has_text=str(hops)).click()
    expected = sample_neighbourhood("customer", hops)
    assert classes(page, ".node.selected") == ["customer"]
    assert set(classes(page, ".node.near")) == expected - {"customer"}
    faded = set(classes(page, ".node.faded"))
    assert faded == set(classes(page, ".node")) - expected
    assert page.locator(".hops button[aria-pressed='true']").text_content() == str(hops)


def test_selection_centres_the_concept(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    select(page, "product")
    box = page.locator(".node[data-id='product'] rect.box").bounding_box()
    canvas = page.locator("svg.graph").bounding_box()
    assert abs(box["x"] + box["width"] / 2 - (canvas["x"] + canvas["width"] / 2)) < 2
    assert abs(box["y"] + box["height"] / 2 - (canvas["y"] + canvas["height"] / 2)) < 2


def test_only_edges_touching_the_selection_are_labelled(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    select(page, "customer")
    visible = page.eval_on_selector_all(
        ".edge-label", "els => els.filter(e => getComputedStyle(e).visibility === 'visible').map(e => e.dataset.id)"
    )
    assert visible and all("customer" in edge_id.split("|")[::2] for edge_id in visible)
    assert "customer|has|order" in visible


def test_states_are_visually_distinct(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    select(page, "customer")
    page.locator(".node[data-id='retention-rate']").hover()  # a neighbour, hovered
    style = """sel => { const s = getComputedStyle(document.querySelector(sel));
                return [s.stroke, s.strokeWidth, s.fill].join(' '); }"""
    selected = page.evaluate(style, ".node[data-id='customer'] .box")
    near = page.evaluate(style, ".node[data-id='order'] .box")
    hover = page.evaluate(style, ".node[data-id='retention-rate'] .box")
    rest = page.evaluate(style, ".node[data-id='product'] .box")
    assert len({selected, near, hover, rest}) == 4
    assert float(page.evaluate("getComputedStyle(document.querySelector(\".node[data-id='product']\")).opacity")) < 1


def test_hover_preview_shows_name_kind_and_first_sentence(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    select(page, "customer")
    page.locator(".node[data-id='order']").hover()
    preview = page.locator(".preview")
    assert preview.is_visible()
    assert preview.locator(".preview-name").text_content() == "Order"
    assert "entity" in preview.locator(".meta").text_content()
    text = preview.locator(".preview-text").text_content()
    assert text.startswith("A customer's request to buy") and text.endswith("single payment.")
    assert classes(page, ".node.selected") == ["customer"], "hovering never changes the selection"
    page.mouse.move(1, 1)
    assert not preview.is_visible()


def test_pane_sections_follow_the_concept_file(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    select(page, "customer")
    pane = page.locator(".pane")
    assert pane.is_visible()
    assert pane.locator("h2").text_content() == "Customer"
    headings = pane.locator("h3").all_text_contents()
    assert headings == [
        "Definition",
        "Discouraged terms",
        "Examples",
        "Non examples",
        "Relations",
        "Implemented in",
        "Incoming relations",
    ]
    assert pane.locator(".definition").evaluate("e => getComputedStyle(e).maxWidth") != "none"
    relations = pane.locator("h3:has-text('Relations') + ul li").all_text_contents()
    assert "Customer has many Orders" in relations
    incoming = pane.locator("h3:has-text('Incoming relations') + ul li").all_text_contents()
    assert "Customer has subtype Active customer" in incoming
    assert "Customer measured by Retention rate" in incoming
    assert pane.locator(".impl .when").first.text_content() == "Never reviewed"
    href = pane.locator(".impl a").first.get_attribute("href")
    assert href == "../../models/marts/dim_customer.sql"


def test_incoming_cardinality_is_flipped_with_the_inverse_label(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    select(page, "order")
    incoming = page.locator(".pane h3:has-text('Incoming relations') + ul li").all_text_contents()
    assert "Order belongs to one Customer" in incoming


def test_proposed_concept_needs_a_definition_and_shows_the_suggestion_apart(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    select(page, "churned-account")
    pane = page.locator(".pane")
    assert pane.locator(".needs").text_content().startswith("Needs a definition.")
    assert "Proposal" in pane.locator("h3").all_text_contents()
    suggestion = pane.locator(".suggestion")
    assert "written by the agent, not a definition" in suggestion.text_content()
    assert pane.locator(".definition").count() == 0, "a suggestion is never shown as the definition"


def test_pane_findings_and_links_move_focus(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    select(page, "subscription")
    findings = page.locator(".pane h3:has-text('Findings') + ul li")
    assert findings.count() == 1 and "I204 · clarity" in findings.text_content()
    assert findings.locator(".badge-icon").get_attribute("data-severity") == "info"
    page.locator(".pane a.concept-link", has_text="Subscription plan").click()
    assert classes(page, ".node.selected") == ["subscription-plan"]


def test_clicking_the_background_clears_the_selection(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    select(page, "customer")
    page.mouse.click(5, 300)
    assert classes(page, ".node.selected") == []
    assert not page.locator(".pane").is_visible()
    assert classes(page, ".node.faded") == []


def test_neighbourhood_query(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    result = page.evaluate(
        """() => {
          const nodes = ['a','b','c','d','e'].map(id => ({id}));
          const edges = [['a','b'],['b','c'],['c','d'],['e','e']].map(([source, target]) => ({source, target}));
          const adj = OntologyGraph.adjacency(nodes, edges);
          return [1, 2, 3].map(h => Object.fromEntries(OntologyGraph.neighbourhood(adj, 'b', h)));
        }"""
    )
    assert result == [{"b": 0, "a": 1, "c": 1}, {"b": 0, "a": 1, "c": 1, "d": 2}, {"b": 0, "a": 1, "c": 1, "d": 2}]


def test_relation_phrases_and_plurals(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    result = page.evaluate(
        """() => [
          OntologyGraph.relationPhrase('has', '1:N', false).verb,
          OntologyGraph.relationPhrase('belongs_to', '1:N', true).verb,
          OntologyGraph.relationPhrase('is_a', null, false).verb,
          OntologyGraph.plural('Order line'), OntologyGraph.plural('Subscription status'),
          OntologyGraph.plural('Category'), OntologyGraph.firstSentence('One. Two.'),
        ]"""
    )
    assert result == [
        "has many",
        "belongs to one",
        "is a",
        "Order lines",
        "Subscription statuses",
        "Categories",
        "One.",
    ]
