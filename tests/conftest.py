"""Shared test helpers: running the CLI and building fixture projects."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO / "skills" / "curating-the-ontology"
ONTO = SKILL_DIR / "scripts" / "onto.py"
FIXTURES = REPO / "tests" / "fixtures"
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


@pytest.fixture
def project(tmp_path: Path) -> Callable[[str | None], Path]:
    return lambda case=None: make_project(tmp_path, case)


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
