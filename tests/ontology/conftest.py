"""Pytest fixtures for the ontology tests. Plain helpers live in ontotest.py."""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from ontotest import SAMPLE, VIEWPORT, Loaded, build, make_project

if TYPE_CHECKING:
    from playwright.sync_api import Browser


@pytest.fixture
def project(tmp_path: Path) -> Callable[[str | None], Path]:
    return lambda case=None: make_project(tmp_path, case)


@pytest.fixture(scope="session")
def sample_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The sample project built once per session, outside the repo."""
    project = tmp_path_factory.mktemp("ui") / "sample"
    shutil.copytree(SAMPLE, project, ignore=shutil.ignore_patterns("index.html"))
    return build(project)


@pytest.fixture
def open_page(browser: Browser) -> Iterator[Callable[..., Loaded]]:
    contexts = []

    def opener(path: Path, viewport: dict[str, int] = VIEWPORT, hash: str = "") -> Loaded:
        context = browser.new_context(viewport=viewport, offline=True)
        contexts.append(context)
        loaded = Loaded(context.new_page())
        loaded.page.goto(path.as_uri() + hash)
        loaded.page.wait_for_function("window.ontologyView && window.ontologyView.ready")
        return loaded

    yield opener
    for context in contexts:
        context.close()
