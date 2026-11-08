"""T1: the CLI shell runs via `uv run --script` from any location."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
from conftest import ONTO, REPO, SKILL_DIR, run_onto

SUBCOMMANDS = [
    ["init"],
    ["new"],
    ["vocab"],
    ["vocab", "new"],
    ["vocab", "new", "kind"],
    ["vocab", "new", "relation"],
    ["vocab", "list"],
    ["review"],
    ["validate"],
    ["impact"],
    ["build"],
]


def run(args: list[str], script: Path = ONTO, cwd: Path = REPO):
    return run_onto(args, cwd=cwd, script=script)


def skill_version() -> str:
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(r'^\s+version:\s*"([^"]+)"', text, re.MULTILINE)
    assert match, "SKILL.md frontmatter must declare metadata.version as a quoted string"
    return match.group(1)


def test_help_lists_every_command() -> None:
    result = run(["--help"])
    assert result.returncode == 0, result.stderr
    for command in ["init", "new", "vocab", "review", "validate", "impact", "build"]:
        assert command in result.stdout


def test_version_matches_skill_frontmatter() -> None:
    result = run(["--version"])
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"onto.py {skill_version()}"


@pytest.mark.parametrize("command", SUBCOMMANDS, ids=" ".join)
def test_every_subcommand_has_help_with_examples(command: list[str]) -> None:
    result = run([*command, "--help"])
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
    assert "Examples:" in result.stdout


def test_unknown_command_is_a_usage_error() -> None:
    result = run(["frobnicate"])
    assert result.returncode == 2
    assert result.stdout == ""
    assert "Error:" in result.stderr
    assert "--help" in result.stderr


def test_unknown_flag_is_a_usage_error() -> None:
    result = run(["validate", "--no-such-flag"])
    assert result.returncode == 2
    assert "Error:" in result.stderr


def test_no_command_prints_help_and_is_a_usage_error() -> None:
    result = run([])
    assert result.returncode == 2
    assert "usage:" in result.stderr


def test_unimplemented_command_says_so() -> None:
    # Replaced command by command as later tasks implement them.
    result = run(["impact"])
    assert result.returncode == 2
    assert "not implemented yet" in result.stderr


def test_runs_from_a_copy_in_a_nested_location(tmp_path: Path) -> None:
    project = tmp_path / "some project" / ".cursor" / "skills"
    copy = project / "curating-the-ontology"
    shutil.copytree(SKILL_DIR, copy, ignore=shutil.ignore_patterns("__pycache__"))
    result = run(["--version"], script=copy / "scripts" / "onto.py", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"onto.py {skill_version()}"
