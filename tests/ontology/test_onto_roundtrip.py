"""Checkpoint 1: the init -> new -> validate round trip in a fresh git repo."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ontotest import findings_json, run_onto


def test_init_new_validate_round_trip(tmp_path: Path) -> None:
    repo = tmp_path / "acme"
    (repo / "models").mkdir(parents=True)
    (repo / "models" / "fct_churn.sql").write_text("select customer_id, is_churned from x\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

    steps = [
        ["init", "--name", "Acme Analytics", "--no-agents-md", "--no-gitattributes"],
        ["new", "customer", "--name", "Customer", "--kind", "entity", "--rationale", "Core of the warehouse."],
        [
            "new",
            "churned-account",
            "--name",
            "Churned account",
            "--kind",
            "entity",
            "--rationale",
            "Introduced in models/fct_churn.sql",
            "--implemented-in",
            "models/fct_churn.sql:is_churned",
        ],
    ]
    for step in steps:
        result = run_onto(step, cwd=repo)
        assert result.returncode == 0, (step, result.stderr)

    validated = run_onto(["validate", "--json"], cwd=repo)
    assert validated.returncode == 0, validated.stderr
    serious = [f for f in findings_json(validated) if f["severity"] in {"error", "warn"}]
    assert serious == []
    assert sorted(p.name for p in (repo / "docs" / "ontology" / "concepts").glob("*.yaml")) == [
        "churned-account.yaml",
        "customer.yaml",
    ]
