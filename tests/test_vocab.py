"""T12: vocabulary extension checks and the `vocab new` / `vocab list` commands."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from conftest import codes_in, collect_findings, findings_json, make_project, run_onto
from ontokit.vocab import insert_extension

MANIFEST = Path("docs/ontology/ontology.yaml")
CODES = ["E005", "E010", "E011", "E012", "W110", "W112", "W113", "I203"]


@pytest.mark.parametrize("code", CODES)
def test_case_triggers_exactly_its_code(tmp_path: Path, code: str) -> None:
    findings = collect_findings(make_project(tmp_path, code.lower()))
    assert codes_in(findings) == {code}, findings


def test_e010_duplicate_and_cross_section_ids(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    manifest = project / MANIFEST
    text = manifest.read_text(encoding="utf-8")
    duplicate = "    measures:\n      status: proposed\n      inverse: measured_by\n"
    kind = "  kinds:\n    placed_by:\n      status: proposed\n"
    text = text.replace("extensions:\n", "extensions:\n" + kind).replace("\nsettings:", duplicate + "\nsettings:")
    manifest.write_text(text, encoding="utf-8")
    messages = [f.message for f in collect_findings(project) if f.code == "E010"]
    assert any("both as a kind and as a relation type" in m for m in messages), messages
    assert any("measures is declared more than once" in m for m in messages), messages


def test_w110_checks_core_attribute_of(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    path = project / "docs/ontology/concepts/order-amount.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("kind: attribute", "kind: metric"), encoding="utf-8")
    [f] = [f for f in collect_findings(project) if f.code == "W110"]
    assert "source of kind 'metric'" in f.message


def test_w113_lists_the_kinds(tmp_path: Path) -> None:
    [f] = collect_findings(make_project(tmp_path, "w113"))
    assert f.concept is None and f.message.startswith("9 kinds are in use")


# --- vocab new -------------------------------------------------------------------------


def vocab_new(project: Path, *args: str):
    return run_onto(["vocab", "new", *args], cwd=project)


def test_vocab_new_kind_adds_only_a_proposed_entry(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    before = (project / MANIFEST).read_text(encoding="utf-8")
    result = vocab_new(project, "kind", "rule", "--rationale", 'Policies recur; "no" core kind fits.')
    assert result.returncode == 0, result.stderr
    after = (project / MANIFEST).read_text(encoding="utf-8")
    entry = yaml.safe_load(after)["extensions"]["kinds"]["rule"]
    assert entry == {
        "status": "proposed",
        "definition": "",
        "proposal": {"rationale": 'Policies recur; "no" core kind fits.'},
    }
    assert after.startswith(before.split("  relation_types:")[0]) and "  relation_types:" in after
    assert findings_json(run_onto(["validate", "--json"], cwd=project)) == [
        {
            "code": "I203",
            "severity": "info",
            "concept": None,
            "criterion": "minimal-commitment",
            "message": "extensions.kinds.rule is declared but nothing uses it. Is it needed?",
        }
    ]


def test_vocab_new_relation_with_constraints(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    result = vocab_new(
        project, "relation", "derived_from", "--inverse", "source_of", "--acyclic",
        "--from", "metric", "--to", "metric", "attribute", "--rationale", "Metrics are computed from metrics.",
    )  # fmt: skip
    assert result.returncode == 0, result.stderr
    entry = yaml.safe_load((project / MANIFEST).read_text(encoding="utf-8"))["extensions"]["relation_types"]
    assert entry["derived_from"] == {
        "status": "proposed",
        "definition": "",
        "inverse": "source_of",
        "acyclic": True,
        "from": ["metric"],
        "to": ["metric", "attribute"],
        "proposal": {"rationale": "Metrics are computed from metrics."},
    }
    assert list(entry) == ["placed_by", "measures", "derived_from"], "appended at the end of the section"


@pytest.mark.parametrize(
    ("args", "code"),
    [
        (["kind", "entity", "--rationale", "x"], 3),
        (["kind", "is_a", "--rationale", "x"], 3),
        (["relation", "measures", "--inverse", "m", "--rationale", "x"], 3),
        (["kind", "measures", "--rationale", "x"], 3),
        (["kind", "Rule", "--rationale", "x"], 2),
        (["kind", "rule", "--rationale", "  "], 2),
        (["relation", "governs", "--inverse", "governed-by", "--rationale", "x"], 2),
        (["relation", "governs", "--inverse", "governed_by", "--from", "policy", "--rationale", "x"], 2),
    ],
)
def test_vocab_new_refusals_change_nothing(tmp_path: Path, args: list[str], code: int) -> None:
    project = make_project(tmp_path)
    before = (project / MANIFEST).read_bytes()
    result = vocab_new(project, *args)
    assert result.returncode == code, result.stderr
    assert result.stderr.startswith("Error: ")
    assert (project / MANIFEST).read_bytes() == before


def test_vocab_new_dry_run_writes_nothing(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    before = (project / MANIFEST).read_bytes()
    result = vocab_new(project, "kind", "rule", "--rationale", "Policies recur.", "--dry-run")
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("rule:\n  status: proposed\n")
    assert "Dry run" in result.stderr
    assert (project / MANIFEST).read_bytes() == before


def test_vocab_new_into_a_fresh_init_manifest_keeps_every_other_byte(tmp_path: Path) -> None:
    project = tmp_path / "fresh"
    project.mkdir()
    assert run_onto(["init", "--name", "Fresh", "--no-agents-md"], cwd=project).returncode == 0
    before = (project / MANIFEST).read_text(encoding="utf-8")
    assert vocab_new(project, "kind", "rule", "--rationale", "Policies recur.").returncode == 0
    assert vocab_new(project, "relation", "has", "--inverse", "belongs_to", "--rationale", "x y").returncode == 0
    after = (project / MANIFEST).read_text(encoding="utf-8")
    added = [line for line in after.splitlines() if line not in before.splitlines()]
    remaining = after
    for line in added:
        remaining = remaining.replace(line + "\n", "", 1)
    assert remaining == before
    data = yaml.safe_load(after)["extensions"]
    assert set(data["kinds"]) == {"rule"} and set(data["relation_types"]) == {"has"}


@pytest.mark.parametrize(
    ("text", "expected_tail"),
    [
        ("schema_version: 1\nname: X\n", "extensions:\n  kinds:\n    new: {}\n"),
        (
            "schema_version: 1\nname: X\n\nsettings:\n  min_definition_words: 8\n",
            "extensions:\n  kinds:\n    new: {}\n\nsettings:\n  min_definition_words: 8\n",
        ),
        ("name: X\nextensions: {}\n", "extensions:\n  kinds:\n    new: {}\n"),
        ("name: X\nextensions:\n  kinds: null  # none yet\n", "extensions:\n  kinds:\n    new: {}\n"),
        (
            "name: X\nextensions:\n    relation_types:\n        r: {}\n",
            "extensions:\n    relation_types:\n        r: {}\n    kinds:\n        new: {}\n",
        ),
        ("name: X\r\nextensions:\r\n  kinds:\r\n", "extensions:\r\n  kinds:\r\n    new: {}\r\n"),
    ],
)
def test_insert_extension_shapes(text: str, expected_tail: str) -> None:
    updated = insert_extension(text, "kinds", lambda indent, eol: f"{indent}new: {{}}{eol}")
    assert updated.endswith(expected_tail), updated
    assert yaml.safe_load(updated)["extensions"]["kinds"] == {"new": {}}


def test_insert_refuses_flow_style() -> None:
    from ontokit.vocab import Refused

    with pytest.raises(Refused, match="inline"):
        insert_extension("extensions:\n  kinds: {rule: {status: proposed}}\n", "kinds", lambda i, e: "")


# --- vocab list -------------------------------------------------------------------------


def test_vocab_list_json(tmp_path: Path) -> None:
    result = run_onto(["vocab", "list", "--json"], cwd=make_project(tmp_path))
    assert result.returncode == 0, result.stderr
    rows = {(r["type"], r["id"]): r for r in json.loads(result.stdout)}
    assert [k for k in rows][:4] == [("kind", "entity"), ("kind", "event"), ("kind", "attribute"), ("kind", "metric")]
    assert rows[("kind", "entity")]["usage"] == 4 and rows[("kind", "entity")]["core"] is True
    assert rows[("relation", "placed_by")] | {"definition": ""} == {
        "type": "relation",
        "id": "placed_by",
        "core": False,
        "status": "defined",
        "definition": "",
        "usage": 2,
        "inverse": "places",
        "acyclic": False,
        "from": ["entity", "event"],
        "to": ["entity"],
    }
    assert rows[("relation", "is_a")]["acyclic"] is True


def test_vocab_list_human(tmp_path: Path) -> None:
    result = run_onto(["vocab", "list"], cwd=make_project(tmp_path))
    assert result.returncode == 0
    assert re.search(r"relation\s+measures\s+extension\s+defined\s+used 1\s+inverse measured_by", result.stdout)
    assert "4 kinds, 6 relation types" in result.stderr


# --- Success criterion 2a ----------------------------------------------------------------


def test_uncommented_starter_extensions_validate_cleanly(tmp_path: Path) -> None:
    project = tmp_path / "fresh"
    project.mkdir()
    assert run_onto(["init", "--name", "Fresh", "--no-agents-md"], cwd=project).returncode == 0
    manifest = project / MANIFEST
    text = manifest.read_text(encoding="utf-8")
    manifest.write_text(re.sub(r"(?m)^(    +)# ?", r"\1", text), encoding="utf-8")
    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))["extensions"]
    assert set(data["kinds"]) == {"rule"}
    assert set(data["relation_types"]) == {"has", "derived_from", "measures"}
    result = run_onto(["validate", "--json"], cwd=project)
    assert result.returncode == 0, result.stdout + result.stderr
    assert {f["severity"] for f in findings_json(result)} <= {"info"}
