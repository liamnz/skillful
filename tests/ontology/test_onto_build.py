"""T8: vendored D3, the build pipeline, the data contract, `build --check` and W108."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

import pytest
from ontotest import REPO, SKILL_DIR, commit_all, findings_json, git, make_project, run_onto

VENDOR = SKILL_DIR / "assets" / "vendor"
SAMPLE = REPO / "examples" / "ontology" / "sample-project"
OUTPUT = Path("docs/ontology/index.html")
DATA = re.compile(r'<script type="application/json" id="ontology-data">\n(.*?)\n</script>', re.DOTALL)


def build(project: Path, *args: str):
    return run_onto(["build", *args], cwd=project)


def page_data(page: str) -> dict:
    match = DATA.search(page)
    assert match, "no embedded data"
    return json.loads(match.group(1))


def built(project: Path) -> str:
    result = build(project)
    assert result.returncode == 0, result.stderr
    return (project / OUTPUT).read_text(encoding="utf-8")


def sample_copy(tmp_path: Path) -> Path:
    project = tmp_path / "sample"
    shutil.copytree(SAMPLE, project, ignore=shutil.ignore_patterns("index.html"))
    return project


# --- Vendored D3 ------------------------------------------------------------------


def test_vendor_files_match_the_manifest() -> None:
    manifest = json.loads((VENDOR / "MANIFEST.json").read_text(encoding="utf-8"))
    modules = manifest["modules"]
    assert [m["order"] for m in modules] == list(range(1, len(modules) + 1))
    assert {m["file"] for m in modules} == {p.name for p in VENDOR.glob("*.js")}
    for module in modules:
        data = (VENDOR / module["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == module["sha256"], module["module"]
        assert re.fullmatch(r"\d+\.\d+\.\d+", module["version"]), "versions are exact"
        assert f"{module['module']}@{module['version']}" in module["source"]
        assert f"v{module['version']}" in data.decode("utf-8").splitlines()[0], "file header names the pinned version"
    assert "ISC" in manifest["license"]["spdx"]
    assert "Permission to use, copy, modify" in (VENDOR / manifest["license"]["file"]).read_text(encoding="utf-8")


def test_vendor_modules_load_after_their_dependencies() -> None:
    manifest = json.loads((VENDOR / "MANIFEST.json").read_text(encoding="utf-8"))
    loaded: set[str] = set()
    for module in sorted(manifest["modules"], key=lambda m: m["order"]):
        text = (VENDOR / module["file"]).read_text(encoding="utf-8")
        needs = set(re.findall(r'require\("(d3-[a-z]+)"\)', text))
        assert needs <= loaded, f"{module['module']} needs {sorted(needs - loaded)} first"
        loaded.add(module["module"])
    assert {"d3-selection", "d3-force", "d3-zoom", "d3-drag", "d3-shape"} <= loaded


# --- The page ---------------------------------------------------------------------


def test_page_is_self_contained(tmp_path: Path) -> None:
    page = built(sample_copy(tmp_path))
    assert not re.search(r"""(?:src|href)\s*=\s*["']?\s*(?:https?:)?//""", page, re.IGNORECASE)
    assert "@import" not in page
    assert "default-src 'none'" in page, "the CSP blocks every network request"
    assert "\r" not in page and page.endswith("</html>\n")
    for module in json.loads((VENDOR / "MANIFEST.json").read_text(encoding="utf-8"))["modules"]:
        assert (VENDOR / module["file"]).read_text(encoding="utf-8").strip() in page
    assert "Permission to use, copy, modify" in page, "the D3 ISC notice is emitted"


def test_page_embeds_the_data_contract(tmp_path: Path) -> None:
    page = built(sample_copy(tmp_path))
    data = page_data(page)
    assert data["schemaVersion"] == 1
    assert data["ontology"]["name"] == "Acme Analytics"
    assert f'<meta name="ontology-input-hash" content="{data["inputHash"]}">' in page
    assert len(data["concepts"]) == 22
    assert sum(len(c["relations"]) for c in data["concepts"]) == 21
    assert [c["id"] for c in data["concepts"]] == sorted(c["id"] for c in data["concepts"])

    customer = next(c for c in data["concepts"] if c["id"] == "customer")
    assert customer["file"] == "concepts/customer.yaml"
    assert customer["relations"][0] == {"type": "has", "target": "order", "cardinality": "1:N"}
    assert customer["implemented_in"][0]["reviewed_date"] is None

    kinds = {k["id"]: k for k in data["vocabulary"]["kinds"]}
    assert kinds["entity"]["encoding"] == {"slot": 1, "shape": "circle"}
    relations = {r["id"]: r for r in data["vocabulary"]["relation_types"]}
    assert relations["is_a"]["core"] and relations["is_a"]["encoding"]["arrow"] == "hollow"
    assert relations["derived_from"]["status"] == "proposed" and not relations["derived_from"]["core"]
    assert relations["measures"]["inverse"] == "measured_by"


def test_embedded_json_cannot_close_its_script_tag(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    concept = next((project / "docs/ontology/concepts").glob("*.yaml"))
    text = concept.read_text(encoding="utf-8")
    question = 'open_questions:\n  - "What about </script><script>alert(1)</script>?"\n'
    concept.write_text(text + question, encoding="utf-8")
    page = built(project)
    assert page.count("</script>") == 3, "only the page's own three script elements close"
    assert any("</script>" in q for c in page_data(page)["concepts"] for q in c["open_questions"])


def test_extension_kinds_get_slots_by_sorted_id(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    manifest = project / "docs/ontology/ontology.yaml"
    text = manifest.read_text(encoding="utf-8")
    kinds = "".join(
        f'    {k}:\n      status: proposed\n      definition: ""\n      proposal: {{rationale: "test"}}\n'
        for k in ("zeta", "alpha", "mu", "beta", "omega")
    )
    manifest.write_text(text.replace("extensions:\n", "extensions:\n  kinds:\n" + kinds, 1), encoding="utf-8")
    encodings = {k["id"]: k["encoding"] for k in page_data(built(project))["vocabulary"]["kinds"]}
    assert encodings["alpha"] == {"slot": 5, "shape": "cross"}
    assert encodings["beta"]["slot"] == 6 and encodings["mu"]["slot"] == 7 and encodings["omega"]["slot"] == 8
    assert encodings["zeta"]["slot"] == "fallback"


# --- Reproducibility --------------------------------------------------------------


def test_builds_in_different_directories_are_byte_identical(tmp_path: Path) -> None:
    first = make_project(tmp_path / "one")
    second = make_project(tmp_path / "a different place")
    assert built(first) == built(second)
    assert built(first) == built(first), "rebuilding changes nothing"


def test_reproducible_at_the_same_git_state(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    git(project, "init", "-q")
    commit_all(project, "initial")
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(project), str(clone))
    assert built(project) == built(clone)


def test_line_endings_do_not_change_the_input_hash(tmp_path: Path) -> None:
    lf = make_project(tmp_path / "lf")
    crlf = make_project(tmp_path / "crlf")
    for path in (crlf / "docs/ontology").rglob("*.yaml"):
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert page_data(built(lf))["inputHash"] == page_data(built(crlf))["inputHash"]


# --- Staleness: build --check and W108 ----------------------------------------------


def test_check_reports_missing_fresh_and_stale(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    missing = build(project, "--check")
    assert missing.returncode == 1 and "has not been built" in missing.stderr
    assert not (project / OUTPUT).exists(), "--check writes nothing"

    built(project)
    fresh = build(project, "--check")
    assert fresh.returncode == 0 and "up to date" in fresh.stderr

    concept = next((project / "docs/ontology/concepts").glob("*.yaml"))
    concept.write_text(concept.read_text(encoding="utf-8") + "open_questions:\n  - New question?\n", encoding="utf-8")
    stale = build(project, "--check")
    assert stale.returncode == 1 and "stale" in stale.stderr


def test_comment_and_formatting_edits_do_not_make_it_stale(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    built(project)
    concept = next((project / "docs/ontology/concepts").glob("*.yaml"))
    concept.write_text("# a new comment\n\n" + concept.read_text(encoding="utf-8"), encoding="utf-8")
    assert build(project, "--check").returncode == 0


def test_validate_reports_w108_only_when_stale(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    never = run_onto(["validate", "--json"], cwd=project)
    assert findings_json(never) == [], "an unbuilt explorer is a note, not a finding"
    assert "has not been built" in never.stderr

    built(project)
    assert findings_json(run_onto(["validate", "--json"], cwd=project)) == []

    manifest = project / "docs/ontology/ontology.yaml"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace("name: ", "name: Renamed ", 1), encoding="utf-8")
    stale = findings_json(run_onto(["validate", "--json"], cwd=project))
    assert [f["code"] for f in stale] == ["W108"]
    assert "Run 'onto.py build'" in stale[0]["message"]

    page = built(project)
    assert all(f["code"] != "W108" for f in page_data(page)["findings"])
    assert findings_json(run_onto(["validate", "--json"], cwd=project)) == []


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    result = build(project, "--dry-run")
    assert result.returncode == 0 and "Would write" in result.stderr
    assert not (project / OUTPUT).exists()


def test_build_embeds_findings_and_still_writes_with_errors(tmp_path: Path) -> None:
    project = make_project(tmp_path, "e002")
    result = build(project)
    assert result.returncode == 0
    assert "error" in result.stderr
    codes = [f["code"] for f in page_data((project / OUTPUT).read_text(encoding="utf-8"))["findings"]]
    assert "E002" in codes


def test_missing_ontology_is_an_environment_error(tmp_path: Path) -> None:
    assert build(tmp_path).returncode == 4


@pytest.mark.parametrize("args", [[], ["--check"]])
def test_committed_sample_view_is_fresh(args: list[str]) -> None:
    if args:
        assert build(SAMPLE, *args).returncode == 0, "rebuild examples/ontology/sample-project and commit it"
    else:
        assert (SAMPLE / OUTPUT).is_file()
