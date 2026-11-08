"""T16: pan and zoom, fit, drag-to-pin, reset, breadcrumbs, deep links and keyboard navigation."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("playwright")


def selected(page) -> list[str]:
    return page.eval_on_selector_all(".node.selected", "els => els.map(e => e.dataset.id)")


def scale(page) -> float:
    return float(page.locator("svg.graph").get_attribute("data-scale"))


def centre(page, concept: str) -> tuple[float, float]:
    box = page.locator(f".node[data-id='{concept}'] rect.box").bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


# --- Pan, zoom, fit, pin, reset -----------------------------------------------------------


def test_wheel_zooms_and_buttons_zoom_and_fit(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    start = scale(page)
    page.mouse.move(400, 300)
    page.mouse.wheel(0, -400)
    page.wait_for_function(f"Number(document.querySelector('svg.graph').dataset.scale) > {start}")
    page.get_by_role("button", name="Zoom out").click()
    page.get_by_role("button", name="Zoom out").click()
    page.get_by_role("button", name="Fit to view").click()
    assert scale(page) == start
    page.get_by_role("button", name="Zoom in").click()
    assert scale(page) == pytest.approx(start * 1.25, rel=0.01)


def test_trackpad_pinch_zooms(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    start = scale(page)
    page.mouse.move(400, 300)
    page.keyboard.down("Control")  # browsers report a pinch as a wheel event with ctrlKey
    page.mouse.wheel(0, -200)
    page.keyboard.up("Control")
    page.wait_for_function(f"Number(document.querySelector('svg.graph').dataset.scale) > {start}")


def test_drag_pans_the_canvas_without_moving_concepts(sample_page: Path, open_page) -> None:
    view = open_page(sample_page)
    page = view.page
    before_positions = view.positions()
    x, y = centre(page, "customer")
    page.mouse.move(5, 400)
    page.mouse.down()
    page.mouse.move(105, 450, steps=5)
    page.mouse.up()
    after_x, after_y = centre(page, "customer")
    assert (after_x - x, after_y - y) == pytest.approx((100, 50), abs=1)
    assert view.positions() == before_positions


def test_drag_pins_a_concept_and_reset_restores_the_layout(sample_page: Path, open_page) -> None:
    view = open_page(sample_page)
    page = view.page
    home = view.positions()
    x, y = centre(page, "product")
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 60, y + 40, steps=5)
    page.mouse.up()
    moved = view.positions()
    assert moved["product"] != home["product"]
    assert {k: v for k, v in moved.items() if k != "product"} == {k: v for k, v in home.items() if k != "product"}
    assert "pinned" in page.locator(".node[data-id='product']").get_attribute("class")
    assert selected(page) == [], "a drag is not a click"
    page.get_by_role("button", name="Reset layout (unpin dragged concepts)").click()
    assert view.positions() == home


# --- Breadcrumbs ---------------------------------------------------------------------------


def test_following_relations_builds_breadcrumbs_that_step_back(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    page.locator(".node[data-id='customer']").click()
    page.locator(".pane a.concept-link", has_text="Orders").click()
    page.locator(".pane a.concept-link", has_text="Refund issued").first.click()
    crumbs = page.locator(".crumbs")
    sep = f" {chr(0x203A)} "  # the breadcrumb separator
    assert crumbs.text_content() == sep.join(["Customer", "Order", "Refund issued"])
    crumbs.locator("a", has_text="Customer").click()
    assert selected(page) == ["customer"]
    assert crumbs.text_content() == "Customer"


# --- Deep links ----------------------------------------------------------------------------


def test_deep_link_restores_selection_hops_and_overlay(sample_page: Path, open_page) -> None:
    page = open_page(sample_page, hash="#customer?hops=2&overlay=health").page
    assert selected(page) == ["customer"]
    assert page.locator(".hops button[aria-pressed='true']").text_content() == "2"
    assert page.evaluate("window.ontologyView.state.overlay") == "health"


def test_url_follows_navigation(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    page.locator(".node[data-id='order']").click()
    assert page.evaluate("location.hash") == "#order"
    page.locator(".hops button", has_text="3").click()
    assert page.evaluate("location.hash") == "#order?hops=3"
    page.go_back()
    page.wait_for_function("location.hash === ''")
    assert selected(page) == []


def test_unknown_deep_link_is_ignored(sample_page: Path, open_page) -> None:
    loaded = open_page(sample_page, hash="#no-such-concept?hops=9")
    assert selected(loaded.page) == [] and loaded.errors == []


# --- Keyboard ------------------------------------------------------------------------------


def focused(page) -> str | None:
    return page.evaluate("document.activeElement.closest && document.activeElement.closest('.node')?.dataset.id")


def test_tab_enters_the_graph_and_enter_selects(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    page.locator(".hops button").last.focus()
    page.keyboard.press("Tab")
    first = focused(page)
    assert first is not None
    ring = page.evaluate(f"""getComputedStyle(document.querySelector(".node[data-id='{first}'] .focus-ring")).stroke""")
    accent = page.evaluate(
        """() => { const probe = document.createElement('div'); probe.style.color = 'var(--accent)';
                   document.body.append(probe); const colour = getComputedStyle(probe).color;
                   probe.remove(); return colour; }"""
    )
    assert ring == accent, "the focus ring uses --accent"
    page.keyboard.press("Enter")
    assert selected(page) == [first]


def test_arrows_and_tab_move_between_connected_concepts(sample_page: Path, open_page) -> None:
    page = open_page(sample_page).page
    page.locator(".node[data-id='customer']").click()
    page.locator(".node[data-id='customer']").focus()
    neighbours = set(
        page.evaluate(
            """ontologyView.model.edges
                 .filter(e => e.source === 'customer' || e.target === 'customer')
                 .map(e => e.source === 'customer' ? e.target : e.source)"""
        )
    )
    for key in ("ArrowRight", "ArrowLeft", "ArrowUp", "ArrowDown"):
        page.locator(".node[data-id='customer']").focus()
        page.keyboard.press(key)
        assert focused(page) in neighbours | {"customer"}
    page.locator(".node[data-id='customer']").focus()
    visited = []
    for _ in neighbours:
        page.keyboard.press("Tab")
        visited.append(focused(page))
    assert set(visited) == neighbours, "Tab steps through every concept connected to the selection"
    page.keyboard.press("Tab")
    assert focused(page) is None, "after the last one, Tab leaves the graph"
    page.locator(".node[data-id='order']").focus()
    page.keyboard.press("Escape")
    assert selected(page) == []
