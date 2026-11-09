"""T13: the `impact` command."""

from __future__ import annotations

import json
from pathlib import Path

from ontotest import REPO, commit_all, git, make_git_project, make_project, run_onto

GOLDEN = REPO / "tests" / "ontology" / "golden" / "impact.json"


def scenario(tmp_path: Path) -> Path:
    """A feature branch with a committed change, an uncommitted change, an untracked file and a record edit."""
    project = make_git_project(tmp_path)
    git(project, "checkout", "-q", "-b", "feature")
    orders = project / "models/fct_orders.sql"
    orders.write_text(orders.read_text(encoding="utf-8") + "-- committed change\n", encoding="utf-8")
    commit_all(project, "feature work")
    customers = project / "models/dim_customer.sql"
    customers.write_text(customers.read_text(encoding="utf-8") + "-- uncommitted change\n", encoding="utf-8")
    (project / "models/fct_refunds.sql").write_text("select 1 as refund_id\n", encoding="utf-8")
    record = project / "docs/ontology/concepts/order.yaml"
    record.write_text(record.read_text(encoding="utf-8") + "open_questions: ['x?']\n", encoding="utf-8")
    return project


def test_impact_json_matches_golden(tmp_path: Path) -> None:
    result = run_onto(["impact", "--json"], cwd=scenario(tmp_path))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert "Compared with main (merge-base " in result.stderr


def test_impact_human_output(tmp_path: Path) -> None:
    result = run_onto(["impact"], cwd=scenario(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "  order-line: models/fct_orders.sql" in result.stdout
    assert result.stdout.rstrip().endswith("possible new concepts):\n  models/fct_refunds.sql")


def test_impact_limit_reports_truncation(tmp_path: Path) -> None:
    result = run_onto(["impact", "--json", "--limit", "1"], cwd=scenario(tmp_path))
    report = json.loads(result.stdout)
    assert [f["path"] for f in report["changed_files"]] == ["models/dim_customer.sql"]
    assert "changed_files: showing 1 of 3" in result.stderr


def test_impact_explicit_base(tmp_path: Path) -> None:
    project = scenario(tmp_path)
    result = run_onto(["impact", "--json", "--base", "feature"], cwd=project)
    paths = [f["path"] for f in json.loads(result.stdout)["changed_files"]]
    assert paths == ["models/dim_customer.sql", "models/fct_refunds.sql"], "only uncommitted and untracked"


def test_impact_with_no_changes(tmp_path: Path) -> None:
    result = run_onto(["impact"], cwd=make_git_project(tmp_path))
    assert result.returncode == 0 and result.stdout.strip() == "No changed files."


def test_impact_without_a_default_branch_asks_for_base(tmp_path: Path) -> None:
    project = make_git_project(tmp_path)
    git(project, "branch", "-m", "trunk")
    result = run_onto(["impact"], cwd=project)
    assert result.returncode == 4
    assert "--base" in result.stderr


def test_impact_unknown_base_and_outside_git(tmp_path: Path) -> None:
    project = make_git_project(tmp_path / "a")
    assert run_onto(["impact", "--base", "nope"], cwd=project).returncode == 4
    outside = make_project(tmp_path / "b")
    result = run_onto(["impact"], cwd=outside)
    assert result.returncode == 4 and "git repository" in result.stderr
