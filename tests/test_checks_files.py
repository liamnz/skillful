"""T13: code-link and staleness checks (E009, W105, W107)."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import (
    codes_in,
    collect_findings,
    commit_all,
    findings_json,
    git,
    make_git_project,
    make_project,
    run_onto,
)

CONCEPTS = Path("docs/ontology/concepts")
OLD = "2020-01-01T12:00:00+00:00"


@pytest.mark.parametrize("code", ["E009", "W105"])
def test_case_triggers_exactly_its_code(tmp_path: Path, code: str) -> None:
    findings = collect_findings(make_project(tmp_path, code.lower()))
    assert codes_in(findings) == {code}, findings


def test_e009_names_the_path(tmp_path: Path) -> None:
    [f] = collect_findings(make_project(tmp_path, "e009"))
    assert f.concept == "refund-reason" and "models/fct_refunds.sql" in f.message and f.criterion == "drift"


def test_w105_found_once_the_symbol_exists(tmp_path: Path) -> None:
    project = make_project(tmp_path, "w105")
    model = project / "models/fct_orders.sql"
    model.write_text(model.read_text(encoding="utf-8").replace("placed_at", "ordered_at"), encoding="utf-8")
    assert collect_findings(project) == []


# --- W107 -------------------------------------------------------------------------------

PROPOSED = (
    "name: Churned account\nkind: entity\nstatus: proposed\ndefinition: ''\n"
    "relations:\n  - {type: is_a, target: customer}\nproposal: {rationale: Seen in a churn model}\n"
)
PROPOSED_KIND = "  kinds:\n    rule:\n      status: proposed\n      proposal: {rationale: Policies recur}\n"


def add_proposals(project: Path) -> None:
    (project / CONCEPTS / "churned-account.yaml").write_text("id: churned-account\n" + PROPOSED, encoding="utf-8")
    manifest = project / "docs/ontology/ontology.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("extensions:\n", "extensions:\n" + PROPOSED_KIND),
        encoding="utf-8",
    )
    concept = project / CONCEPTS / "order.yaml"
    concept.write_text(concept.read_text(encoding="utf-8").replace("kind: entity", "kind: rule"), encoding="utf-8")


def validate(project: Path):
    return run_onto(["validate", "--json"], cwd=project)


def test_w107_old_proposals_by_git_date(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_COMMITTER_DATE", OLD)
    monkeypatch.setenv("GIT_AUTHOR_DATE", OLD)
    project = make_git_project(tmp_path, setup=add_proposals)
    w107 = [f for f in findings_json(validate(project)) if f["code"] == "W107"]
    assert [f["concept"] for f in w107] == [None, "churned-account"]
    assert "extensions.kinds.rule has been proposed for" in w107[0]["message"]
    assert w107[0]["criterion"] == "staleness"


def test_w107_recent_proposals_are_fine(tmp_path: Path) -> None:
    project = make_git_project(tmp_path, setup=add_proposals)
    assert "W107" not in {f["code"] for f in findings_json(validate(project))}


def test_w107_dates_an_extension_by_when_it_was_added(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_COMMITTER_DATE", OLD)
    monkeypatch.setenv("GIT_AUTHOR_DATE", OLD)
    project = make_git_project(tmp_path)  # the manifest is old ...
    monkeypatch.delenv("GIT_COMMITTER_DATE")
    monkeypatch.delenv("GIT_AUTHOR_DATE")
    add_proposals(project)  # ... but the proposals are new
    commit_all(project, "propose")
    assert "W107" not in {f["code"] for f in findings_json(validate(project))}


def test_w107_skipped_outside_git_and_before_commit(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    add_proposals(project)
    result = validate(project)
    assert "W107" not in {f["code"] for f in findings_json(result)}
    assert "W107) skipped: not inside a git repository" in result.stderr

    git(project, "init", "-q")
    commit_all(project, "initial")
    (project / CONCEPTS / "lapsed.yaml").write_text("id: lapsed\n" + PROPOSED.replace("Churned", "Lapsed"), "utf-8")
    result = validate(project)
    assert "not yet committed: lapsed" in result.stderr
