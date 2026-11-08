"""T5: `review` records reviewed_at with a targeted, comment-preserving text edit."""

from __future__ import annotations

from pathlib import Path

import yaml
from conftest import commit_all, git, make_git_project, make_project, run_onto

CONCEPTS = Path("docs") / "ontology" / "concepts"


def record_path(project: Path, concept: str) -> Path:
    return project / CONCEPTS / f"{concept}.yaml"


def set_record(project: Path, concept: str, text: str) -> None:
    record_path(project, concept).write_bytes(text.encode("utf-8"))


def test_inserts_reviewed_at_and_changes_nothing_else(tmp_path: Path) -> None:
    project = make_git_project(tmp_path)
    path = record_path(project, "active-customer")
    before = path.read_text(encoding="utf-8")
    head = git(project, "rev-parse", "HEAD")

    result = run_onto(["review", "active-customer"], cwd=project)
    assert result.returncode == 0, result.stderr
    after = path.read_text(encoding="utf-8")
    assert after == before.replace("    symbol: is_active\n", f"    symbol: is_active\n    reviewed_at: {head}\n")
    assert "active-customer" in result.stdout


def test_replaces_an_existing_reviewed_at(tmp_path: Path) -> None:
    def setup(project: Path) -> None:
        text = record_path(project, "active-customer").read_text(encoding="utf-8")
        set_record(
            project,
            "active-customer",
            text.replace("    symbol: is_active\n", "    symbol: is_active\n    reviewed_at: abc1234  # old review\n"),
        )

    project = make_git_project(tmp_path, setup=setup)
    head = git(project, "rev-parse", "HEAD")
    assert run_onto(["review", "active-customer"], cwd=project).returncode == 0
    text = record_path(project, "active-customer").read_text(encoding="utf-8")
    assert f"    reviewed_at: {head}  # old review\n" in text
    assert "abc1234" not in text


def test_preserves_comments_block_scalars_and_trailing_comments(tmp_path: Path) -> None:
    text = (
        "# Owned by the analytics team\n"
        "id: active-customer\n"
        "name: Active customer\n"
        "kind: entity\n"
        "status: defined\n"
        "definition: >\n"
        "  A customer who has placed at least one paid order in the trailing\n"
        "  ninety days.\n"
        "relations:\n"
        "  - {type: is_a, target: customer}\n"
        "implemented_in:\n"
        "  - path: models/dim_customer.sql   # the mart\n"
        "    symbol: is_active  # flag column\n"
        "  - path: models/fct_orders.sql\n"
        'open_questions: ["Should refunds count?"]\n'
    )
    project = make_git_project(tmp_path, setup=lambda p: set_record(p, "active-customer", text))
    head = git(project, "rev-parse", "HEAD")
    assert run_onto(["review", "active-customer"], cwd=project).returncode == 0
    expected = text.replace(
        "    symbol: is_active  # flag column\n",
        f"    symbol: is_active  # flag column\n    reviewed_at: {head}\n",
    ).replace(
        "  - path: models/fct_orders.sql\n",
        f"  - path: models/fct_orders.sql\n    reviewed_at: {head}\n",
    )
    assert record_path(project, "active-customer").read_text(encoding="utf-8") == expected


def test_flow_style_entry(tmp_path: Path) -> None:
    def setup(project: Path) -> None:
        text = record_path(project, "active-customer").read_text(encoding="utf-8")
        text = text.replace(
            "  - path: models/dim_customer.sql\n    symbol: is_active\n",
            "  - {path: models/dim_customer.sql, symbol: is_active}\n",
        )
        set_record(project, "active-customer", text)

    project = make_git_project(tmp_path, setup=setup)
    head = git(project, "rev-parse", "HEAD")
    assert run_onto(["review", "active-customer"], cwd=project).returncode == 0
    text = record_path(project, "active-customer").read_text(encoding="utf-8")
    assert f"  - {{path: models/dim_customer.sql, symbol: is_active, reviewed_at: {head}}}\n" in text


def test_path_option_reviews_only_that_entry(tmp_path: Path) -> None:
    def setup(project: Path) -> None:
        path = record_path(project, "active-customer")
        path.write_text(path.read_text(encoding="utf-8") + "  - path: models/fct_orders.sql\n", encoding="utf-8")

    project = make_git_project(tmp_path, setup=setup)
    result = run_onto(["review", "active-customer", "--path", "models/fct_orders.sql"], cwd=project)
    assert result.returncode == 0, result.stderr
    data = yaml.safe_load(record_path(project, "active-customer").read_text(encoding="utf-8"))
    by_path = {i["path"]: i for i in data["implemented_in"]}
    assert "reviewed_at" in by_path["models/fct_orders.sql"]
    assert "reviewed_at" not in by_path["models/dim_customer.sql"]


def test_preserves_crlf_line_endings(tmp_path: Path) -> None:
    def setup(project: Path) -> None:
        path = record_path(project, "active-customer")
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))

    project = make_git_project(tmp_path, setup=setup)
    assert run_onto(["review", "active-customer"], cwd=project).returncode == 0
    raw = record_path(project, "active-customer").read_bytes()
    assert b"reviewed_at:" in raw
    assert raw.count(b"\n") == raw.count(b"\r\n")


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    project = make_git_project(tmp_path)
    before = record_path(project, "active-customer").read_bytes()
    result = run_onto(["review", "active-customer", "--dry-run"], cwd=project)
    assert result.returncode == 0, result.stderr
    assert record_path(project, "active-customer").read_bytes() == before
    assert "would" in result.stderr.lower()


def test_unknown_concept_is_refused(tmp_path: Path) -> None:
    result = run_onto(["review", "no-such-concept"], cwd=make_git_project(tmp_path))
    assert result.returncode == 3
    assert "no-such-concept" in result.stderr


def test_unknown_path_is_refused(tmp_path: Path) -> None:
    result = run_onto(["review", "active-customer", "--path", "models/nope.sql"], cwd=make_git_project(tmp_path))
    assert result.returncode == 3
    assert "models/dim_customer.sql" in result.stderr  # lists the paths it does have


def test_concept_without_implementation_is_refused(tmp_path: Path) -> None:
    result = run_onto(["review", "order-amount"], cwd=make_git_project(tmp_path))
    assert result.returncode == 3
    assert "implemented_in" in result.stderr


def test_proposed_concept_is_refused(tmp_path: Path) -> None:
    def setup(project: Path) -> None:
        path = record_path(project, "active-customer")
        path.write_text(path.read_text(encoding="utf-8").replace("status: defined", "status: proposed"), "utf-8")

    result = run_onto(["review", "active-customer"], cwd=make_git_project(tmp_path, setup=setup))
    assert result.returncode == 3
    assert "proposed" in result.stderr


def test_uncommitted_code_change_is_refused(tmp_path: Path) -> None:
    project = make_git_project(tmp_path)
    sql = project / "models" / "dim_customer.sql"
    sql.write_text(sql.read_text(encoding="utf-8") + "-- edit\n", encoding="utf-8")
    result = run_onto(["review", "active-customer"], cwd=project)
    assert result.returncode == 3
    assert "commit" in result.stderr.lower()


def test_outside_git_is_an_environment_error(tmp_path: Path) -> None:
    result = run_onto(["review", "active-customer"], cwd=make_project(tmp_path))
    assert result.returncode == 4


def test_reviewed_record_still_validates(tmp_path: Path) -> None:
    project = make_git_project(tmp_path)
    assert run_onto(["review", "active-customer"], cwd=project).returncode == 0
    commit_all(project, "review")
    result = run_onto(["validate", "--json"], cwd=project)
    assert result.returncode == 0, result.stdout
