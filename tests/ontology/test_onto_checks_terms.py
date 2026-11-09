"""T11: term and definition checks (E007, E008, W101, W102, W103, W109, I201, I202)."""

from __future__ import annotations

from pathlib import Path

import pytest
from ontokit.terms import first_sentence, mentions
from ontotest import codes_in, collect_findings, make_project

CONCEPTS = Path("docs/ontology/concepts")
CODES = ["E007", "E008", "W101", "W102", "W103", "W109", "I201", "I202"]


def add_concept(project: Path, concept_id: str, body: str) -> None:
    (project / CONCEPTS / f"{concept_id}.yaml").write_text(f"id: {concept_id}\n{body}", encoding="utf-8")


def defined(name: str, definition: str, extra: str = "relations:\n  - {type: is_a, target: customer}\n") -> str:
    return f"name: {name}\nkind: entity\nstatus: defined\ndefinition: {definition!r}\n{extra}"


@pytest.mark.parametrize("code", CODES)
def test_case_triggers_exactly_its_code(tmp_path: Path, code: str) -> None:
    findings = collect_findings(make_project(tmp_path, code.lower()))
    assert codes_in(findings) == {code}, findings


# --- Term matching ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "term", "expected"),
    [
        ("A Customer who pays", "customer", True),
        ("a customer's order", "customer", True),
        ("see customer-region", "customer", True),
        ("all customers", "customer", False),
        ("from customers_raw", "customer", False),
        ("from stg_customer", "customer", False),
        ("an active\n  customer", "Active customer", True),
        ("inactive customer", "active customer", False),
        ("", "customer", False),
        ("customer", "  ", False),
    ],
)
def test_terms_match_whole_words_ignoring_case(text: str, term: str, expected: bool) -> None:
    assert mentions(text, term) is expected


def test_first_sentence() -> None:
    assert first_sentence("A thing. It has 3.5 parts.") == "A thing."
    assert first_sentence("No full stop") == "No full stop"


# --- E007 -------------------------------------------------------------------------


def test_e007_reports_every_owner(tmp_path: Path) -> None:
    findings = collect_findings(make_project(tmp_path, "e007"))
    assert sorted(f.concept for f in findings) == ["account", "customer"]
    assert "'customer'" in next(f.message for f in findings if f.concept == "account")


def test_e007_name_against_name_ignores_case_and_spacing(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    add_concept(project, "buyer", defined("ORDER", "Someone who buys things from the store with real money."))
    assert {f.concept for f in collect_findings(project) if f.code == "E007"} == {"buyer", "order"}


def test_e007_near_miss_is_not_a_clash(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    add_concept(project, "orders", defined("Orders", "Every request a buyer ever made to purchase products."))
    assert "E007" not in codes_in(collect_findings(project))


# --- Definitions ------------------------------------------------------------------


def test_e008_only_for_defined_concepts(tmp_path: Path) -> None:
    project = make_project(tmp_path, "e008")
    path = project / CONCEPTS / "prospect.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace("status: defined", "status: proposed\nproposal: {rationale: x}"),
        encoding="utf-8",
    )
    assert codes_in(collect_findings(project)) == set()


def test_w101_uses_min_definition_words(tmp_path: Path) -> None:
    project = make_project(tmp_path, "w101")
    manifest = project / "docs/ontology/ontology.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("min_definition_words: 8", "min_definition_words: 4"),
        encoding="utf-8",
    )
    assert codes_in(collect_findings(project)) == set()


def test_w102_discouraged_term_as_main_term(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    add_concept(
        project,
        "member",
        defined(
            "Member",
            "A loyalty participant is anyone enrolled in the rewards scheme at checkout.",
            "discouraged_terms:\n  - {term: loyalty participant}\nrelations:\n  - {type: is_a, target: customer}\n",
        ),
    )
    [f] = collect_findings(project)
    assert f.code == "W102" and "loyalty participant" in f.message


def test_w102_ignores_own_name_after_the_first_sentence(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    add_concept(
        project,
        "refund",
        defined("Refund", "Money returned to a buyer after a cancelled purchase. A refund may be partial."),
    )
    assert codes_in(collect_findings(project)) == set()


def test_w103_names_the_identifier(tmp_path: Path) -> None:
    [f] = collect_findings(make_project(tmp_path, "w103"))
    assert "'dim_customer'" in f.message


def test_w103_ignores_plain_word_symbols(tmp_path: Path) -> None:
    project = make_project(tmp_path, "w103")
    path = project / CONCEPTS / "customer-region.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace("taken from dim_customer at signup", "chosen by the region team"),
        encoding="utf-8",
    )
    assert codes_in(collect_findings(project)) == set()


def test_w109_checks_rules_and_examples_and_skips_own_terms(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    add_concept(
        project,
        "loyalty",
        defined(
            "Loyalty tier",
            "The reward level a buyer reaches from their total spend over a year.",
            "rules: ['Every Client has exactly one tier']\nexamples: ['Gold for a client spending 5k']\n"
            "relations:\n  - {type: placed_by, target: customer}\n",
        ),
    )
    customer = project / CONCEPTS / "customer.yaml"
    customer.write_text(
        customer.read_text(encoding="utf-8").replace("examples: [", "examples: ['A client of ours', "),
        encoding="utf-8",
    )
    w109 = [f for f in collect_findings(project) if f.code == "W109"]
    assert [f.concept for f in w109] == ["loyalty"], "one finding per term, and never for the owner's own term"
    assert "'Customer'" in w109[0].message


# --- Commitment -------------------------------------------------------------------


def test_i201_incoming_relations_count_as_connected(tmp_path: Path) -> None:
    project = make_project(tmp_path, "i201")
    add_concept(
        project,
        "gift-card-balance",
        "name: Gift card balance\nkind: attribute\nstatus: defined\n"
        "definition: The amount still available to spend on a single prepaid card.\n"
        "relations:\n  - {type: attribute_of, target: gift-card}\n",
    )
    assert codes_in(collect_findings(project)) == set()


def test_i202_not_raised_with_replaced_by(tmp_path: Path) -> None:
    project = make_project(tmp_path, "i202")
    path = project / CONCEPTS / "shopper.yaml"
    path.write_text(path.read_text(encoding="utf-8") + "replaced_by: customer\n", encoding="utf-8")
    assert codes_in(collect_findings(project)) == set()
