"""T17: search with redirects."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("playwright")

ARROW = chr(0x2192)


def results(page) -> list[tuple[str, str, str]]:
    return page.eval_on_selector_all(
        ".search-results li.result", "els => els.map(e => [e.dataset.id, e.dataset.rank, e.textContent.trim()])"
    )


def test_slash_focuses_search_and_enter_moves_the_graph_focus(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    page.locator("svg.graph").click(position={"x": 5, "y": 5})
    page.keyboard.press("/")
    assert page.evaluate("document.activeElement.getAttribute('aria-label')") == "Search concepts and terms"
    page.keyboard.type("order line")
    page.keyboard.press("Enter")
    assert page.eval_on_selector_all(".node.selected", "els => els.map(e => e.dataset.id)") == ["order-line"]
    assert page.evaluate("document.activeElement.closest('.node')?.dataset.id") == "order-line"
    assert not page.locator(".search-results").is_visible()


def test_arrow_keys_choose_a_result(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    page.keyboard.press("/")
    page.keyboard.type("subscription")
    found = results(page)
    assert len(found) >= 3
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowUp")
    assert page.locator(".search-results li[aria-selected='true']").get_attribute("data-id") == found[1][0]
    page.keyboard.press("Enter")
    assert page.eval_on_selector_all(".node.selected", "els => els.map(e => e.dataset.id)") == [found[1][0]]


def test_discouraged_term_is_a_redirect(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    page.keyboard.press("/")
    page.keyboard.type("client")
    found = results(page)
    redirect = next(r for r in found if r[1] == "redirect")
    assert redirect[0] == "customer"
    assert redirect[2] == f"'client' {ARROW} use Customer"
    direct = [r for r in found if r[1] != "redirect"]
    assert direct and direct[0][0] == "client-account", "the deprecated Client account is a direct name match"
    assert found.index(direct[0]) < found.index(redirect), "direct matches rank above redirects"


def test_ranking_is_exact_prefix_redirect_definition(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    ranked = page.evaluate(
        """() => {
          const concepts = [
            {id: 'd', name: 'Zebra', definition: 'Related to an order somehow.', discouraged_terms: []},
            {id: 'c', name: 'Basket', definition: '', discouraged_terms: [{term: 'Order draft'}]},
            {id: 'b', name: 'Order line', definition: '', discouraged_terms: []},
            {id: 'e', name: 'Net order value', definition: '', discouraged_terms: []},
            {id: 'a', name: 'Order', definition: '', discouraged_terms: []},
          ];
          return OntologyGraph.search(concepts, 'order').map(r => [r.id, r.rank]);
        }"""
    )
    assert ranked == [["a", "exact"], ["e", "prefix"], ["b", "prefix"], ["c", "redirect"], ["d", "definition"]]


def test_search_matches_definition_text(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    page.keyboard.press("/")
    page.keyboard.type("checkout")
    assert any(rank == "definition" for _, rank, _ in results(page))


def test_escape_and_no_results(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    page.keyboard.press("/")
    page.keyboard.type("zzzz")
    assert page.locator(".search-results li.none").text_content() == "No matching concepts"
    page.keyboard.press("Escape")
    assert not page.locator(".search-results").is_visible()
    assert page.locator(".search input").input_value() == ""
