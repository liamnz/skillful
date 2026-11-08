"""T26: the skill directory is self-contained, harness-neutral and conforms to the Agent Skills spec.

`skills-ref` (the Agent Skills reference validator) runs with `uvx --offline`, so tests
never download anything. Fetch the pinned version once, with consent:
    uvx --from skills-ref==0.1.1 agentskills --help   (the package installs an `agentskills` command)
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from conftest import REPO, SKILL_DIR, commit_all, git, make_project, run_onto

SKILLS_REF = "skills-ref==0.1.1"
SKILL_MD = SKILL_DIR / "SKILL.md"
REFERENCES = SKILL_DIR / "references"
# Harness-specific features and vocabulary the skill must not use (SPEC "Packaging").
DENYLIST = [
    r"\bhooks?\b",
    r"\bslash[- ]commands?\b",
    r"\bsub-?agents?\b",
    r"\b(?:Bash|Edit|Read|Write|Grep|Glob|MultiEdit|NotebookEdit|TodoWrite|Task) tool\b",
    r"\bTodoWrite\b",
    r"\ballowed-tools\b",
    r"\$CLAUDE_\w+|\$CURSOR_\w+|\bCLAUDE\.md\b",
    r"(?-i:\bClaude Code\b|\bCursor\b)|\.cursor/|\.claude/",  # product names, not CSS `cursor:`
    r"(?m)^\s*/[a-z][\w-]+\s*$",  # a bare slash command on its own line
]


def frontmatter_and_body(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _, front, body = text.split("---\n", 2)
    return yaml.safe_load(front), body


def skill_text_files() -> list[Path]:
    return [
        p
        for p in sorted(SKILL_DIR.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts and "vendor" not in p.parts
    ]


# --- Agent Skills conformance -----------------------------------------------------------------


def test_frontmatter_conforms() -> None:
    front, _ = frontmatter_and_body(SKILL_MD)
    assert set(front) <= {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
    assert "allowed-tools" not in front, "allowed-tools is experimental and harness-specific"
    assert front["name"] == SKILL_DIR.name
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", front["name"]) and len(front["name"]) <= 64
    assert 0 < len(front["description"]) <= 1024
    assert "Use when" in front["description"], "the description says when to use the skill"
    assert len(front["compatibility"]) <= 500
    assert re.fullmatch(r"\d+\.\d+\.\d+", front["metadata"]["version"])


def test_skills_ref_validate_passes() -> None:
    result = subprocess.run(
        ["uvx", "--offline", "--from", SKILLS_REF, "agentskills", "validate", str(SKILL_DIR)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        stdin=subprocess.DEVNULL,
        timeout=120,
    )
    output = (result.stderr + result.stdout).lower()
    offline_miss = result.returncode != 0 and ("offline" in output or "network was disabled" in output)
    if offline_miss:
        pytest.skip(f"{SKILLS_REF} is not cached; fetch it once with: uvx --from {SKILLS_REF} agentskills --help")
    assert result.returncode == 0, result.stdout + result.stderr


def test_skill_md_body_is_short_and_links_resolve_one_level_deep() -> None:
    _, body = frontmatter_and_body(SKILL_MD)
    assert len(body.splitlines()) < 500
    assert len(body.split()) < 3800, "about 5k tokens at most"
    links = re.findall(r"\]\(([^)]+)\)", body)
    assert links, "SKILL.md links its references"
    for link in links:
        assert not re.match(r"[a-z]+:|/", link), f"{link} must be relative"
        assert re.fullmatch(r"references/[\w-]+\.md", link), f"{link} must be one level deep"
        assert (SKILL_DIR / link).is_file(), f"{link} does not resolve"
    linked = {Path(link).name for link in links}
    assert linked == {p.name for p in REFERENCES.glob("*.md")}, "every reference is linked, and nothing else"


def test_each_reference_has_a_when_to_read_trigger() -> None:
    _, body = frontmatter_and_body(SKILL_MD)
    for ref in REFERENCES.glob("*.md"):
        assert re.search(rf"\[references/{ref.name}\]\(references/{ref.name}\)[^\n]*\n?[^\n]*\bread\b", body, re.I), (
            ref.name
        )


def test_references_do_not_link_onward() -> None:
    for ref in REFERENCES.glob("*.md"):
        text = ref.read_text(encoding="utf-8")
        assert not re.search(r"\]\([^)]*\.md\)", text), f"{ref.name} links to another file"
        assert "references/" not in text, f"{ref.name} points at another reference"


@pytest.mark.parametrize("path", skill_text_files(), ids=lambda p: p.relative_to(SKILL_DIR).as_posix())
def test_no_harness_specific_vocabulary(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    hits = [m.group(0) for pattern in DENYLIST for m in re.finditer(pattern, text, flags=re.I)]
    assert hits == [], f"harness-specific terms: {hits}"


def test_hard_rules_come_first() -> None:
    _, body = frontmatter_and_body(SKILL_MD)
    headings = re.findall(r"(?m)^## (.+)$", body)
    assert headings[0] == "Hard rules"
    rules = body.split("## Hard rules", 1)[1].split("\n## ", 1)[0]
    for phrase in ("definition", "status: defined", "Canonical terms", "consent", "review"):
        assert phrase.lower() in rules.lower(), phrase


def test_gruber_reference_maps_every_code_to_its_criterion() -> None:
    from ontokit.findings import CODES

    sections = re.split(r"(?m)^## ", (REFERENCES / "gruber-criteria.md").read_text(encoding="utf-8"))[1:]
    titles = {
        "Clarity": {"clarity"},
        "Coherence": {"coherence"},
        "Extendibility": {"extendibility"},
        "Minimal encoding bias": {"minimal-encoding-bias"},
        "Minimal ontological commitment": {"minimal-commitment"},
        "Drift and staleness (added by this skill)": {"drift", "staleness"},
        "Structural findings": {None},
    }
    placed: dict[str, str] = {}
    for section in sections:
        title = section.splitlines()[0].strip()
        for code in set(re.findall(r"\b[EWI]\d{3}\b", section)):
            assert CODES[code][1] in titles[title], f"{code} is listed under {title}"
            placed[code] = title
    assert set(placed) == set(CODES), f"not mapped: {sorted(set(CODES) - set(placed))}"


# --- Self-contained -----------------------------------------------------------------------


def test_skill_references_nothing_outside_itself() -> None:
    outside = re.compile(r"\.\./|(?<![\w/])(?:tests|examples|tasks)/|SPEC\.md|ontologising")
    for path in skill_text_files():
        hits = outside.findall(path.read_text(encoding="utf-8", errors="replace"))
        assert hits == [], f"{path.relative_to(SKILL_DIR)} refers outside the skill: {hits}"


def test_vendor_directory_holds_only_listed_files() -> None:
    vendor = SKILL_DIR / "assets" / "vendor"
    manifest = json.loads((vendor / "MANIFEST.json").read_text(encoding="utf-8"))
    listed = {m["file"] for m in manifest["modules"]} | {"MANIFEST.json", manifest["license"]["file"]}
    assert {p.name for p in vendor.iterdir()} == listed


@pytest.mark.parametrize("where", [".cursor/skills", ".agents/skills", "tools/ai/vendor/skills with spaces"])
def test_runs_from_a_copy_anywhere(tmp_path: Path, where: str) -> None:
    """Copy the skill into the project and run every command from the project root."""
    project = make_project(tmp_path)
    copy = project / where / SKILL_DIR.name
    shutil.copytree(SKILL_DIR, copy, ignore=shutil.ignore_patterns("__pycache__"))
    script = copy / "scripts" / "onto.py"
    git(project, "init", "-q")
    commit_all(project, "initial")

    def onto(*args: str) -> subprocess.CompletedProcess[str]:
        result = run_onto(list(args), cwd=project, script=script)
        assert result.returncode == 0, f"{args}: {result.stderr}"
        return result

    onto("--version")
    onto("validate", "--json")
    onto("vocab", "list", "--json")
    onto("vocab", "new", "kind", "rule", "--rationale", "Policies recur.")
    onto("new", "refund", "--name", "Refund", "--kind", "event", "--implemented-in", "models/fct_orders.sql")
    onto("impact", "--json", "--base", "HEAD")
    onto("review", "customer")
    onto("build")
    onto("build", "--check")
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    git(fresh, "init", "-q")
    result = run_onto(["init", "--name", "Fresh", "--agents-md", "--gitattributes"], cwd=fresh, script=script)
    assert result.returncode == 0, result.stderr
    assert (fresh / "docs/ontology/ontology.yaml").is_file() and (fresh / "AGENTS.md").is_file()
    page = (project / "docs/ontology/index.html").read_text(encoding="utf-8")
    assert "Permission to use, copy, modify" in page


def test_the_copy_does_not_reach_into_this_repo(tmp_path: Path) -> None:
    """A copy works with this repository's files out of reach: nothing resolves via the repo."""
    copy = tmp_path / "isolated" / SKILL_DIR.name
    shutil.copytree(SKILL_DIR, copy, ignore=shutil.ignore_patterns("__pycache__"))
    for path in copy.rglob("*.py"):
        assert str(REPO) not in path.read_text(encoding="utf-8")
    result = run_onto(["--help"], cwd=tmp_path, script=copy / "scripts" / "onto.py")
    assert result.returncode == 0 and "onto.py" in result.stdout
