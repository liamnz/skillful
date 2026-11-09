"""T10: relation checks (E004, E006, E013, E014, W104, W111, I204)."""

from __future__ import annotations

from pathlib import Path

import pytest
from ontotest import codes_in, collect_findings, make_project

ONTOLOGY = Path("docs/ontology")


def add_concept(project: Path, concept_id: str, body: str) -> None:
    (project / ONTOLOGY / "concepts" / f"{concept_id}.yaml").write_text(f"id: {concept_id}\n{body}", encoding="utf-8")


def concept(name: str, kind: str, relations: str, status: str = "defined") -> str:
    return (
        f"name: {name}\nkind: {kind}\nstatus: {status}\n"
        "definition: A deliberately plain test definition that is long enough to pass.\n"
        f"relations:\n{relations}"
    )


@pytest.mark.parametrize("code", ["E004", "E006", "E013", "E014", "W104", "W111", "I204"])
def test_case_triggers_exactly_its_code(tmp_path: Path, code: str) -> None:
    findings = collect_findings(make_project(tmp_path, code.lower()))
    assert codes_in(findings) == {code}, findings


def test_baseline_is_clean(tmp_path: Path) -> None:
    assert collect_findings(make_project(tmp_path)) == []


def test_e004_names_the_missing_target(tmp_path: Path) -> None:
    [f] = collect_findings(make_project(tmp_path, "e004"))
    assert f.concept == "lapsed-customer" and f.criterion == "coherence"
    assert "loyalty-programme" in f.message


def test_e006_reports_the_cycle_path_once(tmp_path: Path) -> None:
    [f] = collect_findings(make_project(tmp_path, "e006"))
    assert f.concept == "loyal-customer"
    assert "loyal-customer → vip-customer → loyal-customer" in f.message


def test_e006_finds_longer_cycles_and_self_loops(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    add_concept(project, "a", concept("A", "entity", "  - {type: part_of, target: b}\n"))
    add_concept(project, "b", concept("B", "entity", "  - {type: part_of, target: c}\n"))
    add_concept(project, "c", concept("C", "entity", "  - {type: part_of, target: a}\n"))
    add_concept(project, "d", concept("D", "entity", "  - {type: part_of, target: d}\n"))
    cycles = [f.message for f in collect_findings(project) if f.code == "E006"]
    assert len(cycles) == 2
    assert any("a → b → c → a" in m for m in cycles)
    assert any("d → d" in m for m in cycles)


def test_e006_applies_to_acyclic_extensions(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    manifest = project / ONTOLOGY / "ontology.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "  relation_types:\n",
            "  relation_types:\n    derived_from:\n      status: defined\n"
            "      definition: The source is computed from the target and changes when the target does.\n"
            "      inverse: source_of\n      acyclic: true\n",
        ),
        encoding="utf-8",
    )
    add_concept(project, "m1", concept("M one", "metric", "  - {type: derived_from, target: m2}\n"))
    add_concept(project, "m2", concept("M two", "metric", "  - {type: derived_from, target: m1}\n"))
    [f] = [f for f in collect_findings(project) if f.code == "E006"]
    assert "'derived_from'" in f.message and "m1 → m2 → m1" in f.message


def test_non_acyclic_types_may_loop(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    add_concept(project, "x", concept("X", "entity", "  - {type: placed_by, target: y}\n"))
    add_concept(project, "y", concept("Y", "entity", "  - {type: placed_by, target: x}\n"))
    assert "E006" not in codes_in(collect_findings(project))


@pytest.mark.parametrize(
    ("relation", "expected"),
    [
        ("{type: is_a, target: customer, cardinality: '1:1'}", True),
        ("{type: attribute_of, target: customer, cardinality: 'N:1'}", True),
        ("{type: related_to, target: customer, cardinality: '1:N'}", True),
        ("{type: related_to, target: customer, cardinality: 'N:1'}", True),
        ("{type: related_to, target: customer, cardinality: '1:1'}", False),
        ("{type: related_to, target: customer, cardinality: 'N:M'}", False),
        ("{type: part_of, target: customer, cardinality: 'N:1'}", False),
        ("{type: placed_by, target: customer, cardinality: '1:N'}", False),
    ],
)
def test_e013_cardinality_rules(tmp_path: Path, relation: str, expected: bool) -> None:
    project = make_project(tmp_path)
    kind = "attribute" if "attribute_of" in relation else "entity"
    add_concept(project, "thing", concept("Thing", kind, f"  - {relation}\n"))
    assert ("E013" in codes_in(collect_findings(project))) is expected


def test_e014_symmetric_relation_stated_on_both_ends(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    add_concept(project, "p", concept("P", "entity", "  - {type: related_to, target: q, cardinality: '1:1'}\n"))
    add_concept(project, "q", concept("Q", "entity", "  - {type: related_to, target: p, cardinality: 'N:M'}\n"))
    e014 = [f for f in collect_findings(project) if f.code == "E014"]
    assert [f.concept for f in e014] == ["p", "q"]
    assert "1:1 on 'p'" in e014[0].message and "N:M on 'q'" in e014[0].message


def test_e014_ignores_agreeing_or_missing_cardinality(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    add_concept(project, "p", concept("P", "entity", "  - {type: related_to, target: q, cardinality: 'N:M'}\n"))
    add_concept(project, "q", concept("Q", "entity", "  - {type: related_to, target: p, cardinality: 'N:M'}\n"))
    add_concept(project, "r", concept("R", "entity", "  - {type: related_to, target: p}\n"))
    assert "E014" not in codes_in(collect_findings(project))


def test_w104_suggests_the_replacement(tmp_path: Path) -> None:
    [f] = collect_findings(make_project(tmp_path, "w104"))
    assert f.concept == "support-ticket" and "'customer' instead" in f.message


def test_w104_not_raised_between_deprecated_concepts(tmp_path: Path) -> None:
    project = make_project(tmp_path, "w104")
    ticket = project / ONTOLOGY / "concepts" / "support-ticket.yaml"
    ticket.write_text(
        ticket.read_text(encoding="utf-8").replace("status: defined", "status: deprecated\nreplaced_by: order"),
        encoding="utf-8",
    )
    assert "W104" not in codes_in(collect_findings(project))


def test_w111_names_both_kinds(tmp_path: Path) -> None:
    [f] = collect_findings(make_project(tmp_path, "w111"))
    assert "(event)" in f.message and "(entity)" in f.message


def test_unknown_relation_types_are_left_to_e005(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    add_concept(project, "z", concept("Z", "entity", "  - {type: owns, target: z, cardinality: '1:N'}\n"))
    assert codes_in(collect_findings(project)) & {"E006", "E013", "E014"} == set()
