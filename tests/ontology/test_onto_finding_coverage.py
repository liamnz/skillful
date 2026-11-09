"""Checkpoint 3: every finding code has a fixture that triggers it, and the baseline triggers none.

The code list comes from the registry (ontokit.findings.CODES), which must match the
spec's table. Most codes have a static case in tests/fixtures/cases/<code>/. The
git- and build-based ones (W106, W107, W108, I205) are set up here in a temp repo.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest
from ontokit.findings import CODES
from ontotest import (
    CASES,
    REPO,
    codes_in,
    collect_findings,
    commit_all,
    findings_json,
    make_git_project,
    make_project,
    run_onto,
)

ONTOLOGY = Path("docs/ontology")
OLD = "2020-01-01T12:00:00+00:00"


def validate_codes(project: Path) -> set[str]:
    return {f["code"] for f in findings_json(run_onto(["validate", "--json"], cwd=project))}


def w106(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    project = make_git_project(tmp_path)
    model = project / "models/dim_customer.sql"
    model.write_text(model.read_text(encoding="utf-8").replace("'90 days'", "'30 days'"), encoding="utf-8")
    return project


def w107(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    def propose(project: Path) -> None:
        (project / ONTOLOGY / "concepts" / "lapsed.yaml").write_text(
            "id: lapsed\nname: Lapsed\nkind: entity\nstatus: proposed\ndefinition: ''\n"
            "relations: [{type: is_a, target: customer}]\nproposal: {rationale: seen in code}\n",
            encoding="utf-8",
        )

    monkeypatch.setenv("GIT_COMMITTER_DATE", OLD)
    monkeypatch.setenv("GIT_AUTHOR_DATE", OLD)
    return make_git_project(tmp_path, setup=propose)


def w108(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    project = make_project(tmp_path)
    assert run_onto(["build"], cwd=project).returncode == 0
    record = project / ONTOLOGY / "concepts" / "order.yaml"
    record.write_text(record.read_text(encoding="utf-8") + "open_questions: ['Can an order be split?']\n", "utf-8")
    return project


def i205(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    project = make_git_project(tmp_path)
    record = project / ONTOLOGY / "concepts" / "active-customer.yaml"
    record.write_text(
        record.read_text(encoding="utf-8").replace(
            "symbol: is_active", "symbol: is_active\n    reviewed_at: " + "deadbeef" * 5
        ),
        encoding="utf-8",
    )
    commit_all(project, "a review recorded against a commit that is not in history")
    return project


SCENARIOS: dict[str, Callable[[Path, pytest.MonkeyPatch], Path]] = {
    "W106": w106,
    "W107": w107,
    "W108": w108,
    "I205": i205,
}


def test_registry_matches_the_spec_table() -> None:
    spec = (REPO / "docs" / "ontology-skill" / "SPEC.md").read_text(encoding="utf-8")
    table = dict(re.findall(r"^\| ([EWI]\d{3}) \| (error|warn|info) \|", spec, flags=re.MULTILINE))
    assert table == {code: severity for code, (severity, _) in CODES.items()}


def test_every_code_has_a_way_to_trigger_it() -> None:
    static = {p.name.upper() for p in CASES.iterdir() if p.is_dir() and re.fullmatch(r"[ewi]\d{3}", p.name)}
    assert set(CODES) == static | set(SCENARIOS), "add a fixture case or a scenario for each new code"
    assert not static & set(SCENARIOS)


@pytest.mark.parametrize("code", sorted(CODES))
def test_code_is_triggered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: str) -> None:
    if code in SCENARIOS:
        assert code in validate_codes(SCENARIOS[code](tmp_path, monkeypatch))
    else:
        assert code in codes_in(collect_findings(make_project(tmp_path, code.lower())))


def test_baseline_triggers_none_even_in_git_with_a_fresh_build(tmp_path: Path) -> None:
    def built(project: Path) -> None:
        assert run_onto(["build"], cwd=project).returncode == 0

    project = make_git_project(tmp_path, setup=built)
    result = run_onto(["validate", "--json", "--strict"], cwd=project)
    assert result.returncode == 0, result.stdout + result.stderr
    assert findings_json(result) == []
