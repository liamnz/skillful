"""T2: loading, schema validation and the `validate` command (E001-E003)."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import findings_json, make_project, run_onto
from ontokit.findings import Finding, sort_findings

ERRORS_AND_WARNINGS = {"error", "warn"}


def validate(project: Path, *extra: str):
    return run_onto(["validate", "--json", *extra], cwd=project)


def test_baseline_has_no_findings(tmp_path: Path) -> None:
    result = validate(make_project(tmp_path))
    assert result.returncode == 0, result.stderr
    assert findings_json(result) == []


@pytest.mark.parametrize("code", ["E001", "E002", "E003"])
def test_case_triggers_exactly_its_code(tmp_path: Path, code: str) -> None:
    result = validate(make_project(tmp_path, code.lower()))
    findings = findings_json(result)
    codes = {f["code"] for f in findings if f["severity"] in ERRORS_AND_WARNINGS}
    assert codes == {code}, findings
    assert result.returncode == 1


def test_e001_names_the_file_and_line(tmp_path: Path) -> None:
    [finding] = findings_json(validate(make_project(tmp_path, "e001")))
    assert finding["concept"] == "broken"
    assert "concepts/broken.yaml" in finding["message"]
    assert "line" in finding["message"]


def test_e002_lists_each_schema_violation(tmp_path: Path) -> None:
    findings = findings_json(validate(make_project(tmp_path, "e002")))
    messages = " ".join(f["message"] for f in findings)
    assert "'kind' is a required property" in messages
    assert "colour" in messages


def test_e003_id_must_match_filename(tmp_path: Path) -> None:
    [finding] = findings_json(validate(make_project(tmp_path, "e003")))
    assert finding["concept"] == "vip-customer"
    assert "valued-customer" in finding["message"]


def test_e003_duplicate_id(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    concepts = project / "docs" / "ontology" / "concepts"
    (concepts / "client.yaml").write_text((concepts / "customer.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    findings = findings_json(validate(project))
    assert [f["code"] for f in findings] == ["E003"]
    assert "duplicate" in findings[0]["message"].lower()


def test_manifest_schema_violation_is_e002(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    manifest = project / "docs" / "ontology" / "ontology.yaml"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace("name: Baseline\n", ""), encoding="utf-8")
    findings = findings_json(validate(project))
    assert [f["code"] for f in findings] == ["E002"]
    assert findings[0]["concept"] is None
    assert "ontology.yaml" in findings[0]["message"]


def test_missing_ontology_is_an_environment_error(tmp_path: Path) -> None:
    result = run_onto(["validate"], cwd=tmp_path)
    assert result.returncode == 4
    assert "init" in result.stderr


def test_root_option_points_elsewhere(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    (project / "docs" / "ontology").rename(project / "ontology")
    result = run_onto(["validate", "--json", "--root", "ontology"], cwd=project)
    assert result.returncode == 0, result.stderr


def test_human_output_goes_to_stdout_and_summary_to_stderr(tmp_path: Path) -> None:
    result = run_onto(["validate"], cwd=make_project(tmp_path, "e002"))
    assert "E002" in result.stdout
    assert "2 errors, 0 warnings, 0 info" in result.stderr


def test_clean_human_output(tmp_path: Path) -> None:
    result = run_onto(["validate"], cwd=make_project(tmp_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert "no findings" in result.stderr.lower()


def test_findings_sort_by_severity_concept_then_code() -> None:
    findings = [
        Finding("I201", "info", "a", None, "m"),
        Finding("W101", "warn", "b", None, "m"),
        Finding("E004", "error", "b", None, "m"),
        Finding("E002", "error", "b", None, "m"),
        Finding("E002", "error", None, None, "m"),
        Finding("W101", "warn", "a", None, "m"),
    ]
    ordered = [(f.code, f.concept) for f in sort_findings(findings)]
    assert ordered == [
        ("E002", None),
        ("E002", "b"),
        ("E004", "b"),
        ("W101", "a"),
        ("W101", "b"),
        ("I201", "a"),
    ]
