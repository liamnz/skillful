"""T6: the sample project validates with only its deliberate findings."""

from __future__ import annotations

import yaml
from conftest import REPO, findings_json, run_onto

SAMPLE = REPO / "examples" / "ontology" / "sample-project"


def test_sample_project_has_only_deliberate_findings() -> None:
    result = run_onto(["validate", "--json"], cwd=SAMPLE)
    assert result.returncode == 0, result.stdout + result.stderr
    allowed = yaml.safe_load((SAMPLE / "expected-findings.yaml").read_text(encoding="utf-8"))["allowed"]
    allowed_keys = {(a["code"], a["concept"]) for a in allowed}
    unexpected = [f for f in findings_json(result) if (f["code"], f["concept"]) not in allowed_keys]
    assert unexpected == [], unexpected


def test_sample_project_covers_what_the_view_and_evals_need() -> None:
    files = sorted((SAMPLE / "docs" / "ontology" / "concepts").glob("*.yaml"))
    concepts = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in files]
    assert 15 <= len(concepts) <= 25
    assert {c["kind"] for c in concepts} == {"entity", "event", "attribute", "metric"}
    assert {c["status"] for c in concepts} == {"defined", "proposed", "deprecated"}
    relations = [r for c in concepts for r in c.get("relations", [])]
    assert any("cardinality" in r for r in relations)
    assert any(r["type"] == "related_to" for r in relations)
    assert any(c.get("discouraged_terms") for c in concepts)
    assert any(c.get("open_questions") for c in concepts)
    assert any(c.get("proposal", {}).get("suggested_definition") for c in concepts)

    for concept in concepts:
        for impl in concept.get("implemented_in", []):
            assert (SAMPLE / impl["path"]).is_file(), impl["path"]

    # The contradiction eval (d) relies on.
    active = next(c for c in concepts if c["id"] == "active-customer")
    assert "90 days" in active["definition"]
    assert "30 days" in (SAMPLE / "models/marts/dim_customer.sql").read_text(encoding="utf-8")
