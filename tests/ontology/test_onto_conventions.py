"""T14: script conventions across every command, and golden output.

Regenerate the golden files after an intended output change with:
    UPDATE_GOLDEN=1 uv run --with pytest --with pyyaml --with jsonschema \
        pytest tests/ontology/test_onto_conventions.py -q
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from ontotest import REPO, make_git_project, make_project, run_onto

GOLDEN = REPO / "tests" / "ontology" / "golden"
MANIFEST = Path("docs/ontology/ontology.yaml")


def assert_golden(name: str, stdout: str) -> None:
    path = GOLDEN / name
    actual = json.loads(stdout)
    if os.environ.get("UPDATE_GOLDEN"):
        path.write_text(json.dumps(actual, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    assert actual == json.loads(path.read_text(encoding="utf-8")), f"{name} differs from the golden file"


# --- Golden JSON --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("case", "golden", "exit_code"), [(None, "validate-baseline.json", 0), ("multi", "validate-multi.json", 1)]
)
def test_validate_json_golden(tmp_path: Path, case: str | None, golden: str, exit_code: int) -> None:
    result = run_onto(["validate", "--json"], cwd=make_project(tmp_path, case))
    assert result.returncode == exit_code, result.stderr
    assert_golden(golden, result.stdout)


def test_vocab_list_json_golden(tmp_path: Path) -> None:
    result = run_onto(["vocab", "list", "--json"], cwd=make_project(tmp_path))
    assert result.returncode == 0, result.stderr
    assert_golden("vocab-list.json", result.stdout)


# --- validate --strict and --limit --------------------------------------------------------


def test_warnings_exit_0_unless_strict(tmp_path: Path) -> None:
    project = make_project(tmp_path, "w101")
    assert run_onto(["validate"], cwd=project).returncode == 0
    assert run_onto(["validate", "--strict"], cwd=project).returncode == 1


def test_info_never_fails_strict(tmp_path: Path) -> None:
    assert run_onto(["validate", "--strict"], cwd=make_project(tmp_path, "i204")).returncode == 0


def test_limit_caps_findings_and_says_so(tmp_path: Path) -> None:
    result = run_onto(["validate", "--json", "--limit", "2"], cwd=make_project(tmp_path, "multi"))
    assert [f["code"] for f in json.loads(result.stdout)] == ["E004", "W109"]
    assert "Showing 2 of 4 findings (--limit 2)" in result.stderr
    assert result.returncode == 1, "the exit code reflects every finding, not just those shown"


def test_negative_limit_is_a_usage_error(tmp_path: Path) -> None:
    result = run_onto(["validate", "--limit", "-1"], cwd=make_project(tmp_path))
    assert result.returncode == 2 and "--limit" in result.stderr


# --- schema_version ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "command", [["validate"], ["build"], ["vocab", "list"], ["new", "x", "--name", "X", "--kind", "entity"]]
)
def test_newer_schema_version_is_refused_with_advice(tmp_path: Path, command: list[str]) -> None:
    project = make_project(tmp_path)
    manifest = project / MANIFEST
    manifest.write_text(manifest.read_text(encoding="utf-8").replace("schema_version: 1", "schema_version: 2"), "utf-8")
    result = run_onto(command, cwd=project)
    assert result.returncode == 4
    assert "uses schema_version 2, but this skill reads schema_version 1" in result.stderr
    assert "Update the skill" in result.stderr


# --- Exit codes 0-4 ----------------------------------------------------------------------


def test_each_exit_code(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    assert run_onto(["validate"], cwd=project).returncode == 0
    assert run_onto(["validate"], cwd=make_project(tmp_path / "e", "e004")).returncode == 1
    assert run_onto(["validate", "--bogus"], cwd=project).returncode == 2
    assert run_onto(["new", "customer", "--name", "C", "--kind", "entity"], cwd=project).returncode == 3
    nowhere = tmp_path / "nowhere"
    nowhere.mkdir()
    assert run_onto(["validate"], cwd=nowhere).returncode == 4


# --- Sweep: --help, closed stdin, --dry-run ------------------------------------------------

COMMANDS = [
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


@pytest.mark.parametrize("command", COMMANDS, ids=" ".join)
def test_every_command_has_help_with_examples(command: list[str]) -> None:
    result = run_onto([*command, "--help"], timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("usage: onto.py")
    if command not in (["vocab"], ["vocab", "new"]):
        assert "Examples:" in result.stdout


WRITE_COMMANDS = [
    ["init", "--name", "Fresh", "--agents-md", "--gitattributes"],
    ["new", "churned-account", "--name", "Churned account", "--kind", "entity", "--rationale", "seen in code"],
    ["vocab", "new", "kind", "rule", "--rationale", "policies recur"],
    ["vocab", "new", "relation", "governs", "--inverse", "governed_by", "--rationale", "limits recur"],
    ["review", "active-customer"],
    ["build"],
]


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".git" not in p.relative_to(root).parts
    }


@pytest.mark.parametrize("command", WRITE_COMMANDS, ids=lambda c: " ".join(c[:3]))
def test_dry_run_writes_nothing(tmp_path: Path, command: list[str]) -> None:
    project = make_git_project(tmp_path)
    if command[0] == "init":
        project = tmp_path / "empty"
        project.mkdir()
    before = snapshot(project)
    result = run_onto([*command, "--dry-run"], cwd=project, timeout=60)  # stdin is closed: nothing may wait for input
    assert result.returncode == 0, result.stderr
    assert snapshot(project) == before


@pytest.mark.parametrize("command", [["validate"], ["vocab", "list"], ["impact"], ["build", "--check"]])
def test_read_commands_finish_with_stdin_closed(tmp_path: Path, command: list[str]) -> None:
    result = run_onto(command, cwd=make_git_project(tmp_path), timeout=60)
    assert result.returncode in (0, 1), result.stderr
