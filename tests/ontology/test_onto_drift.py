"""T5: W106 drift detection and I205, against real temporary git repositories."""

from __future__ import annotations

from pathlib import Path

from ontotest import commit_all, findings_json, make_git_project, make_project, run_onto

CONCEPTS = Path("docs") / "ontology" / "concepts"

# A dim_customer.sql long enough that "near" (drift_context_lines: 3) is meaningful.
#   line 2: customer_id   (symbol of `customer`)
#   line 6: is_active     (symbol of `active-customer`)
#   lines 12-30: unrelated columns
DIM_CUSTOMER = (
    "select\n"
    "    customer_id,\n"
    "    region,\n"
    "    signup_date,\n"
    "    -- activity\n"
    "    last_paid_order_at >= current_date - interval '90 days' as is_active,\n"
    "    7 as padding_a,\n"
    "    8 as padding_b,\n"
    "    9 as padding_c,\n"
    "    10 as padding_d,\n"
    "    11 as padding_e,\n" + "".join(f"    {n} as unrelated_{n},\n" for n in range(12, 31)) + "    0 as last_column\n"
    "from {{ ref('stg_customers') }}\n"
)


def long_models(project: Path) -> None:
    (project / "models" / "dim_customer.sql").write_text(DIM_CUSTOMER, encoding="utf-8")


def edit_line(project: Path, line_no: int, new_text: str, file: str = "models/dim_customer.sql") -> None:
    path = project / file
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    lines[line_no - 1] = new_text + "\n"
    path.write_text("".join(lines), encoding="utf-8")


def drift(project: Path) -> dict[str, list[dict]]:
    """Concept id -> W106/I205 findings."""
    result = run_onto(["validate", "--json"], cwd=project)
    out: dict[str, list[dict]] = {}
    for f in findings_json(result):
        if f["code"] in {"W106", "I205"}:
            out.setdefault(f["concept"], []).append(f)
    return out


def review(project: Path, concept: str) -> None:
    result = run_onto(["review", concept], cwd=project)
    assert result.returncode == 0, result.stderr


def test_clean_repo_has_no_drift(tmp_path: Path) -> None:
    assert drift(make_git_project(tmp_path, setup=long_models)) == {}


def test_unrelated_edit_elsewhere_in_shared_file_does_not_fire(tmp_path: Path) -> None:
    project = make_git_project(tmp_path, setup=long_models)
    edit_line(project, 25, "    25 as renamed_unrelated,")
    commit_all(project)
    assert drift(project) == {}


def test_edit_near_symbol_fires(tmp_path: Path) -> None:
    project = make_git_project(tmp_path, setup=long_models)
    edit_line(project, 8, "    8 as padding_b_changed,")  # 2 lines below is_active
    commit_all(project)
    found = drift(project)
    assert set(found) == {"active-customer"}
    [finding] = found["active-customer"]
    assert finding["code"] == "W106"
    assert finding["criterion"] == "drift"
    assert "models/dim_customer.sql" in finding["message"]
    assert "review active-customer" in finding["message"]


def test_edit_just_outside_context_does_not_fire(tmp_path: Path) -> None:
    project = make_git_project(tmp_path, setup=long_models)
    edit_line(project, 10, "    10 as padding_d_changed,")  # 4 lines below is_active
    commit_all(project)
    assert drift(project) == {}


def test_removing_the_symbol_line_fires(tmp_path: Path) -> None:
    project = make_git_project(tmp_path, setup=long_models)
    edit_line(project, 6, "    false as dormant,")
    commit_all(project)
    assert set(drift(project)) == {"active-customer"}


def test_uncommitted_change_near_symbol_fires(tmp_path: Path) -> None:
    project = make_git_project(tmp_path, setup=long_models)
    edit_line(project, 6, "    last_paid_order_at >= current_date - interval '30 days' as is_active,")
    assert set(drift(project)) == {"active-customer"}


def test_without_symbol_any_change_fires(tmp_path: Path) -> None:
    def setup(project: Path) -> None:
        long_models(project)
        record = project / CONCEPTS / "order-amount.yaml"
        record.write_text(
            record.read_text(encoding="utf-8") + "implemented_in:\n  - path: models/fct_orders.sql\n",
            encoding="utf-8",
        )

    project = make_git_project(tmp_path, setup=setup)
    path = project / "models" / "fct_orders.sql"
    path.write_text(path.read_text(encoding="utf-8") + "-- trailing comment\n", encoding="utf-8")
    commit_all(project)
    assert "order-amount" in drift(project)


def test_review_clears_the_finding(tmp_path: Path) -> None:
    project = make_git_project(tmp_path, setup=long_models)
    edit_line(project, 6, "    false as is_active,")
    commit_all(project)
    assert "active-customer" in drift(project)
    review(project, "active-customer")
    assert drift(project) == {}


def test_unrelated_concept_edit_does_not_clear_once_reviewed(tmp_path: Path) -> None:
    project = make_git_project(tmp_path, setup=long_models)
    review(project, "active-customer")
    commit_all(project, "review")
    edit_line(project, 6, "    false as is_active,")
    commit_all(project, "code change")

    record = project / CONCEPTS / "active-customer.yaml"
    record.write_text(record.read_text(encoding="utf-8") + 'examples: ["A recent buyer"]\n', encoding="utf-8")
    commit_all(project, "unrelated concept edit")
    assert set(drift(project)) == {"active-customer"}


def test_without_reviewed_at_the_concept_files_last_commit_is_the_baseline(tmp_path: Path) -> None:
    project = make_git_project(tmp_path, setup=long_models)
    edit_line(project, 6, "    false as is_active,")
    commit_all(project, "code change")
    assert "active-customer" in drift(project)

    record = project / CONCEPTS / "active-customer.yaml"
    record.write_text(record.read_text(encoding="utf-8") + 'examples: ["A recent buyer"]\n', encoding="utf-8")
    commit_all(project, "concept edit")
    assert drift(project) == {}


def test_unreachable_reviewed_at_reports_i205_and_falls_back(tmp_path: Path) -> None:
    def setup(project: Path) -> None:
        long_models(project)
        record = project / CONCEPTS / "active-customer.yaml"
        text = record.read_text(encoding="utf-8").replace(
            "    symbol: is_active\n", "    symbol: is_active\n    reviewed_at: deadbeefdeadbeef\n"
        )
        record.write_text(text, encoding="utf-8")

    project = make_git_project(tmp_path, setup=setup)
    assert {f["code"] for f in drift(project)["active-customer"]} == {"I205"}

    edit_line(project, 6, "    false as is_active,")
    commit_all(project)
    found = drift(project)["active-customer"]
    assert {f["code"] for f in found} == {"I205", "W106"}
    i205 = next(f for f in found if f["code"] == "I205")
    assert i205["severity"] == "info"
    assert "deadbeef" in i205["message"]


def test_proposed_concepts_are_skipped(tmp_path: Path) -> None:
    def setup(project: Path) -> None:
        long_models(project)
        record = project / CONCEPTS / "active-customer.yaml"
        record.write_text(
            record.read_text(encoding="utf-8").replace("status: defined", "status: proposed"), encoding="utf-8"
        )

    project = make_git_project(tmp_path, setup=setup)
    edit_line(project, 6, "    false as is_active,")
    commit_all(project)
    assert drift(project) == {}


def test_outside_git_is_skipped_with_a_notice(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    result = run_onto(["validate", "--json"], cwd=project)
    assert result.returncode == 0
    assert findings_json(result) == []
    assert "git" in result.stderr.lower()
    assert "skipped" in result.stderr.lower()


def test_uncommitted_concept_file_is_skipped_with_a_notice(tmp_path: Path) -> None:
    project = make_git_project(tmp_path, setup=long_models)
    (project / CONCEPTS / "dormant-customer.yaml").write_text(
        "id: dormant-customer\nname: Dormant customer\nkind: entity\nstatus: defined\n"
        "definition: A customer with no paid orders in the trailing ninety days.\n"
        "relations:\n  - {type: is_a, target: customer}\n"
        "implemented_in:\n  - path: models/dim_customer.sql\n    symbol: is_active\n",
        encoding="utf-8",
    )
    result = run_onto(["validate", "--json"], cwd=project)
    assert [f for f in findings_json(result) if f["code"] == "W106"] == []
    assert "dormant-customer" in result.stderr
