"""T4: `new` creates status=proposed concept stubs, and nothing else."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from ontokit.schema import schema_errors
from ontotest import findings_json, make_project, run_onto

CONCEPTS = Path("docs") / "ontology" / "concepts"


def new(project: Path, *args: str):
    return run_onto(["new", *args], cwd=project)


def load(project: Path, concept_id: str) -> dict:
    return yaml.safe_load((project / CONCEPTS / f"{concept_id}.yaml").read_text(encoding="utf-8"))


def test_creates_schema_valid_proposed_stub(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    result = new(
        project,
        "churned-account",
        "--name",
        "Churned account",
        "--kind",
        "entity",
        "--rationale",
        "Introduced as churned_account in models/fct_orders.sql",
        "--suggested-definition",
        "A customer who has cancelled every subscription.",
        "--implemented-in",
        "models/fct_orders.sql:customer_id",
    )
    assert result.returncode == 0, result.stderr
    assert "concepts/churned-account.yaml" in result.stdout

    record = load(project, "churned-account")
    assert schema_errors("concept", record) == []
    assert record["id"] == "churned-account"
    assert record["status"] == "proposed"
    assert record["definition"] == ""
    assert record["proposal"] == {
        "rationale": "Introduced as churned_account in models/fct_orders.sql",
        "suggested_definition": "A customer who has cancelled every subscription.",
    }
    assert record["implemented_in"] == [{"path": "models/fct_orders.sql", "symbol": "customer_id"}]
    assert "own words" in result.stderr  # reminds the agent who writes definitions


def test_stub_keeps_the_ontology_free_of_errors_and_warnings(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    new(project, "refund", "--name", "Refund", "--kind", "event", "--rationale", "Seen in a new model.")
    findings = findings_json(run_onto(["validate", "--json"], cwd=project))
    assert [f for f in findings if f["severity"] in {"error", "warn"}] == []


def test_minimal_stub_has_no_proposal_block(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    assert new(project, "refund", "--name", "Refund", "--kind", "event").returncode == 0
    assert "proposal" not in load(project, "refund")


def test_yaml_special_characters_round_trip(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    name = 'Net revenue: "booked"'
    rationale = "Uses # and: colons\nacross two lines"
    assert new(project, "net-revenue", "--name", name, "--kind", "metric", "--rationale", rationale).returncode == 0
    record = load(project, "net-revenue")
    assert record["name"] == name
    assert record["proposal"]["rationale"] == rationale


def test_existing_id_is_refused(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    before = (project / CONCEPTS / "customer.yaml").read_bytes()
    result = new(project, "customer", "--name", "Customer", "--kind", "entity")
    assert result.returncode == 3
    assert "already exists" in result.stderr
    assert (project / CONCEPTS / "customer.yaml").read_bytes() == before


def test_status_cannot_be_set(tmp_path: Path) -> None:
    result = new(make_project(tmp_path), "refund", "--name", "Refund", "--kind", "event", "--status", "defined")
    assert result.returncode == 2


@pytest.mark.parametrize("bad_id", ["Refund", "refund_request", "refund-", "refund--request", "refund.yaml"])
def test_invalid_id_is_a_usage_error(tmp_path: Path, bad_id: str) -> None:
    result = new(make_project(tmp_path), bad_id, "--name", "Refund", "--kind", "event")
    assert result.returncode == 2
    assert "kebab-case" in result.stderr


def test_unknown_kind_lists_the_valid_kinds(tmp_path: Path) -> None:
    result = new(make_project(tmp_path), "refund", "--name", "Refund", "--kind", "measure")
    assert result.returncode == 2
    assert 'Received: "measure"' in result.stderr
    for kind in ("entity", "event", "attribute", "metric"):
        assert kind in result.stderr
    assert "vocab list" in result.stderr


def test_declared_kind_extension_is_accepted(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    manifest = project / "docs" / "ontology" / "ontology.yaml"
    text = manifest.read_text(encoding="utf-8").replace(
        "extensions:\n",
        'extensions:\n  kinds:\n    rule:\n      status: proposed\n      definition: ""\n',
    )
    manifest.write_text(text, encoding="utf-8")
    assert new(project, "refund-limit", "--name", "Refund limit", "--kind", "rule").returncode == 0


def test_empty_name_is_a_usage_error(tmp_path: Path) -> None:
    result = new(make_project(tmp_path), "refund", "--name", "  ", "--kind", "event")
    assert result.returncode == 2


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("models/fct_orders.sql", {"path": "models/fct_orders.sql"}),
        ("models/fct_orders.sql:order_id", {"path": "models/fct_orders.sql", "symbol": "order_id"}),
        ("models\\fct_orders.sql:order_id", {"path": "models/fct_orders.sql", "symbol": "order_id"}),
        ("./models/fct_orders.sql", {"path": "models/fct_orders.sql"}),
    ],
)
def test_implemented_in_parsing(tmp_path: Path, spec: str, expected: dict) -> None:
    project = make_project(tmp_path)
    result = new(project, "refund", "--name", "Refund", "--kind", "event", "--implemented-in", spec)
    assert result.returncode == 0, result.stderr
    assert load(project, "refund")["implemented_in"] == [expected]


@pytest.mark.parametrize("spec", ["C:/repo/models/x.sql", "/abs/models/x.sql", "models/x.sql:", "../outside.sql"])
def test_implemented_in_rejects_non_repo_relative_paths(tmp_path: Path, spec: str) -> None:
    result = new(make_project(tmp_path), "refund", "--name", "Refund", "--kind", "event", "--implemented-in", spec)
    assert result.returncode == 2
    assert "--implemented-in" in result.stderr


def test_missing_implementation_file_warns_but_creates(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    result = new(project, "refund", "--name", "Refund", "--kind", "event", "--implemented-in", "models/nope.sql")
    assert result.returncode == 0
    assert "does not exist" in result.stderr


def test_dry_run_prints_the_record_and_writes_nothing(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    result = new(project, "refund", "--name", "Refund", "--kind", "event", "--dry-run")
    assert result.returncode == 0, result.stderr
    assert not (project / CONCEPTS / "refund.yaml").exists()
    assert "would create" in result.stderr
    assert yaml.safe_load(result.stdout)["status"] == "proposed"


def test_no_ontology_is_an_environment_error(tmp_path: Path) -> None:
    result = new(tmp_path, "refund", "--name", "Refund", "--kind", "event")
    assert result.returncode == 4
    assert "init" in result.stderr
