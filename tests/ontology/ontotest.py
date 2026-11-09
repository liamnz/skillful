"""Helpers for the ontology tests: running the CLI and building fixture projects.

Named uniquely so another skill's test suite can sit beside this one. Pytest fixtures
stay in conftest.py.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page

REPO = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO / "skills" / "curating-the-ontology"
ONTO = SKILL_DIR / "scripts" / "onto.py"
FIXTURES = REPO / "tests" / "ontology" / "fixtures"
BASELINE = FIXTURES / "baseline"
CASES = FIXTURES / "cases"

# In-process access to ontokit for unit tests.
sys.path.insert(0, str(SKILL_DIR / "scripts"))


def run_onto(
    args: list[str], cwd: Path = REPO, script: Path = ONTO, timeout: int = 120
) -> subprocess.CompletedProcess[str]:
    """Run the CLI exactly as an agent would: via `uv run --script`, stdin closed."""
    return subprocess.run(
        ["uv", "run", "--quiet", "--script", str(script), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        stdin=subprocess.DEVNULL,
        timeout=timeout,
    )


def _ignore(directory: str, names: list[str]) -> set[str]:
    return {n for n in names if n in {"__pycache__", "README.md"}}


def make_project(tmp_path: Path, case: str | None = None) -> Path:
    """Copy the baseline into tmp_path and overlay a case's files (added or replaced)."""
    project = tmp_path / "project"
    shutil.copytree(BASELINE, project, ignore=_ignore)
    if case is not None:
        overlay = CASES / case
        assert overlay.is_dir(), f"no fixture case {case!r}"
        shutil.copytree(overlay, project, dirs_exist_ok=True, ignore=_ignore)
    return project


def collect_findings(project: Path) -> list:
    """Every finding for a project, in process and without git: fast, for check tests.

    Runs from the project root, as the CLI does, so implemented_in paths resolve.
    """
    from contextlib import chdir

    from ontokit.context import Context
    from ontokit.validate import collect

    with chdir(project):
        return collect(Path("docs/ontology"), Context(git=None))


def codes_in(findings: list) -> set[str]:
    return {f.code for f in findings}


def findings_json(result: subprocess.CompletedProcess[str]) -> list[dict]:
    return json.loads(result.stdout)


GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


def git(repo: Path, *args: str) -> str:
    """Run git in `repo` with a fixed identity; return stdout."""
    import os

    env = {**os.environ, **GIT_ENV}
    result = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-c", "init.defaultBranch=main", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=True,
    )
    return result.stdout.strip()


def commit_all(repo: Path, message: str = "change") -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--allow-empty", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def make_git_project(tmp_path: Path, case: str | None = None, setup: Callable[[Path], None] | None = None) -> Path:
    """A baseline project (plus optional case overlay and setup edits) as a git repo with one commit."""
    project = make_project(tmp_path, case)
    if setup is not None:
        setup(project)
    git(project, "init", "-q")
    commit_all(project, "initial")
    return project


# --- Browser (UI) tests: used only by modules that import playwright -------------------------

SAMPLE = REPO / "examples" / "ontology" / "sample-project"
OUTPUT = Path("docs/ontology/index.html")
VIEWPORT = {"width": 1280, "height": 720}  # the minimum supported viewport


def build(project: Path) -> Path:
    result = run_onto(["build"], cwd=project)
    assert result.returncode == 0, result.stderr
    return project / OUTPUT


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
