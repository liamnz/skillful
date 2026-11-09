"""T3: `init` scaffolds docs/ontology/ with a manifest that has no active extensions."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml
from conftest import findings_json, run_onto

ONTOLOGY = Path("docs") / "ontology"


def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "acme-warehouse"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    return repo


def snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def uncomment_starters(manifest: str) -> str:
    """Uncomment every commented line inside the extensions block, as an editor's toggle-comment would."""
    lines = manifest.splitlines(keepends=True)
    start = next(i for i, line in enumerate(lines) if line.startswith("extensions:"))
    end = next(i for i, line in enumerate(lines) if line.startswith("settings:"))
    for i in range(start, end):
        lines[i] = re.sub(r"^(\s*)# ?", r"\1", lines[i]) if lines[i].strip().startswith("#") else lines[i]
    return "".join(lines)


def test_init_then_validate_is_clean(tmp_path: Path) -> None:
    repo = git_repo(tmp_path)
    result = run_onto(["init", "--name", "Acme Analytics", "--no-agents-md", "--no-gitattributes"], cwd=repo)
    assert result.returncode == 0, result.stderr
    assert (repo / ONTOLOGY / "ontology.yaml").is_file()
    assert (repo / ONTOLOGY / "concepts").is_dir()
    # concepts/ must survive a commit even while empty
    assert (repo / ONTOLOGY / "concepts" / ".gitkeep").is_file()

    validated = run_onto(["validate", "--json"], cwd=repo)
    assert validated.returncode == 0, validated.stderr
    assert findings_json(validated) == []


def test_manifest_has_name_and_no_active_extensions(tmp_path: Path) -> None:
    repo = git_repo(tmp_path)
    run_onto(["init", "--name", 'Acme: "Analytics"'], cwd=repo)  # YAML-special characters
    data = yaml.safe_load((repo / ONTOLOGY / "ontology.yaml").read_text(encoding="utf-8"))
    assert data["name"] == 'Acme: "Analytics"'
    assert data["schema_version"] == 1
    assert not (data.get("extensions") or {}).get("kinds")
    assert not (data.get("extensions") or {}).get("relation_types")


def test_default_name_is_the_repo_folder(tmp_path: Path) -> None:
    repo = git_repo(tmp_path)
    run_onto(["init"], cwd=repo)
    data = yaml.safe_load((repo / ONTOLOGY / "ontology.yaml").read_text(encoding="utf-8"))
    assert data["name"] == "acme-warehouse"


def test_starter_extensions_validate_when_uncommented(tmp_path: Path) -> None:
    repo = git_repo(tmp_path)
    run_onto(["init"], cwd=repo)
    manifest = repo / ONTOLOGY / "ontology.yaml"
    text = manifest.read_text(encoding="utf-8")
    for starter in ("rule:", "has:", "derived_from:", "measures:"):
        assert f"# {starter}" in text
    manifest.write_text(uncomment_starters(text), encoding="utf-8")

    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    assert set(data["extensions"]["kinds"]) == {"rule"}
    assert set(data["extensions"]["relation_types"]) == {"has", "derived_from", "measures"}
    # Starters arrive as proposals: humans write the definition and promote them.
    assert all(ext["status"] == "proposed" for ext in data["extensions"]["kinds"].values())

    validated = run_onto(["validate", "--json"], cwd=repo)
    serious = [f for f in findings_json(validated) if f["severity"] in {"error", "warn"}]
    assert serious == [], serious
    assert validated.returncode == 0


def test_rerun_is_idempotent(tmp_path: Path) -> None:
    repo = git_repo(tmp_path)
    run_onto(["init", "--name", "First"], cwd=repo)
    before = snapshot(repo / ONTOLOGY)
    result = run_onto(["init", "--name", "Second"], cwd=repo)
    assert result.returncode == 0, result.stderr
    assert snapshot(repo / ONTOLOGY) == before
    assert "already exists" in result.stderr
    assert "--name" in result.stderr  # tells the user the name was not applied


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    repo = git_repo(tmp_path)
    result = run_onto(["init", "--dry-run"], cwd=repo)
    assert result.returncode == 0, result.stderr
    assert not (repo / "docs").exists()
    assert "would create" in result.stdout
    assert "ontology.yaml" in result.stdout


def test_hints_when_consent_flags_are_missing(tmp_path: Path) -> None:
    repo = git_repo(tmp_path)
    result = run_onto(["init"], cwd=repo)
    assert "--agents-md" in result.stderr
    assert "--gitattributes" in result.stderr
    assert not (repo / "AGENTS.md").exists()
    assert not (repo / ".gitattributes").exists()


def test_no_hints_when_consent_flags_given(tmp_path: Path) -> None:
    repo = git_repo(tmp_path)
    result = run_onto(["init", "--no-agents-md", "--no-gitattributes"], cwd=repo)
    assert "--agents-md" not in result.stderr
    assert "--gitattributes" not in result.stderr


def test_written_files_use_lf_line_endings(tmp_path: Path) -> None:
    repo = git_repo(tmp_path)
    run_onto(["init"], cwd=repo)
    assert b"\r\n" not in (repo / ONTOLOGY / "ontology.yaml").read_bytes()


# --- T23: --agents-md and --gitattributes ---------------------------------------------------

START = "<!-- curating-the-ontology:start"
END = "<!-- curating-the-ontology:end -->"
ATTRIBUTE = "docs/ontology/index.html -diff linguist-generated=true"


def init(repo: Path, *flags: str):
    return run_onto(["init", *flags], cwd=repo)


def test_agents_md_is_created_with_the_marked_section(tmp_path: Path) -> None:
    repo = git_repo(tmp_path)
    result = init(repo, "--agents-md", "--no-gitattributes")
    assert result.returncode == 0, result.stderr
    text = (repo / "AGENTS.md").read_text(encoding="utf-8")
    assert text.startswith(START) and text.rstrip().endswith(END)
    assert "`docs/ontology/`" in text and "curating-the-ontology" in text
    assert "created AGENTS.md" in result.stdout


def test_agents_md_section_is_added_and_updated_in_place(tmp_path: Path) -> None:
    repo = git_repo(tmp_path)
    before, after = "# Agents\n\nHouse rules here.\n", "\n## Later section\nKeep me.\n"
    (repo / "AGENTS.md").write_text(before, encoding="utf-8", newline="\n")
    assert init(repo, "--agents-md").returncode == 0
    first = (repo / "AGENTS.md").read_text(encoding="utf-8")
    assert first.startswith(before + "\n" + START)
    # Someone adds text after the section and edits inside it; re-running restores only the section.
    edited = first.replace("Use the canonical", "Use the CANONICAL") + after
    (repo / "AGENTS.md").write_text(edited, encoding="utf-8", newline="\n")
    result = init(repo, "--agents-md")
    assert result.returncode == 0 and "updated AGENTS.md" in result.stdout
    second = (repo / "AGENTS.md").read_text(encoding="utf-8")
    assert second == first + after, "only the marked section changes"
    assert second.count(START) == 1
    third = init(repo, "--agents-md")
    assert "already has the ontology section" in third.stderr
    assert (repo / "AGENTS.md").read_text(encoding="utf-8") == second


def test_agents_md_keeps_crlf_line_endings(tmp_path: Path) -> None:
    repo = git_repo(tmp_path)
    (repo / "AGENTS.md").write_bytes(b"# Agents\r\n")
    assert init(repo, "--agents-md").returncode == 0
    raw = (repo / "AGENTS.md").read_bytes()
    assert raw.startswith(b"# Agents\r\n\r\n<!-- curating") and b"\n" not in raw.replace(b"\r\n", b"")


def test_broken_markers_are_refused_before_any_write(tmp_path: Path) -> None:
    repo = git_repo(tmp_path)
    (repo / "AGENTS.md").write_text(f"{START} -->\nhalf a section\n", encoding="utf-8")
    before = snapshot(repo)
    result = init(repo, "--agents-md", "--gitattributes")
    assert result.returncode == 3 and "markers" in result.stderr
    assert snapshot(repo) == before


def test_gitattributes_line_is_added_once(tmp_path: Path) -> None:
    repo = git_repo(tmp_path)
    (repo / ".gitattributes").write_text("* text=auto", encoding="utf-8", newline="\n")
    assert init(repo, "--gitattributes").returncode == 0
    assert (repo / ".gitattributes").read_text(encoding="utf-8") == f"* text=auto\n{ATTRIBUTE}\n"
    result = init(repo, "--gitattributes")
    assert "already has the index.html line" in result.stderr
    assert (repo / ".gitattributes").read_text(encoding="utf-8").count(ATTRIBUTE) == 1


def test_gitattributes_follows_root(tmp_path: Path) -> None:
    repo = git_repo(tmp_path)
    assert init(repo, "--root", "ontology", "--gitattributes", "--agents-md").returncode == 0
    assert (repo / ".gitattributes").read_text(
        encoding="utf-8"
    ) == "ontology/index.html -diff linguist-generated=true\n"
    assert "`ontology/`" in (repo / "AGENTS.md").read_text(encoding="utf-8")


def test_no_flags_and_no_dash_flags_change_nothing(tmp_path: Path) -> None:
    repo = git_repo(tmp_path)
    (repo / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
    for flags in ([], ["--no-agents-md", "--no-gitattributes"]):
        init(repo, *flags)
        assert (repo / "AGENTS.md").read_text(encoding="utf-8") == "# Agents\n"
        assert not (repo / ".gitattributes").exists()


def test_dry_run_writes_neither_file(tmp_path: Path) -> None:
    repo = git_repo(tmp_path)
    (repo / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
    before = snapshot(repo)
    result = init(repo, "--agents-md", "--gitattributes", "--dry-run")
    assert result.returncode == 0
    assert "would update AGENTS.md" in result.stdout and "would create .gitattributes" in result.stdout
    assert snapshot(repo) == before
