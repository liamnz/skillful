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
