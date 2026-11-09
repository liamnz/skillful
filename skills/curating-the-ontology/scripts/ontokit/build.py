"""The `build` command: write the self-contained docs/ontology/index.html explorer.

The page inlines the design tokens, the app's CSS and JS, the vendored D3 modules
and one JSON blob (the data contract below). It loads nothing from the network,
and the same records and git state always produce byte-identical output: no
timestamps, sorted keys and records, LF line endings.

Data contract (schemaVersion 1), embedded as <script type="application/json" id="ontology-data">:
  schemaVersion, skillVersion, inputHash
  ontology:   {name, description, schema_version, path_to_project}
  vocabulary: {kinds: [...], relation_types: [...]}, core first, then extensions by id;
              each entry has id, core, status, definition, encoding (+ relation fields)
  concepts:   records as in the YAML (snake_case keys), sorted by id, plus `file`;
              each implemented_in entry also has `reviewed_date` (git committer date or null)
  findings:   every validator finding except W108, which is about this page itself
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from . import ASSETS_DIR, skill_version
from .checks import run_checks
from .context import Context
from .findings import EXIT_ENVIRONMENT, EXIT_FINDINGS, EXIT_OK, Finding, sort_findings
from .gitinfo import Git
from .io import Concept, Ontology, OntologyUnavailable, display_path, load
from .staleness import OUTPUT_FILE, built_hash, hash_meta, input_hash

SCHEMA_VERSION = 1
HTML_DIR = ASSETS_DIR / "html"
VENDOR_DIR = ASSETS_DIR / "vendor"

# Extension kinds take slots 5-8 by sorted id; each gets a shape no core kind uses.
EXTENSION_SHAPES = ("cross", "star", "wye", "hexagon")
FALLBACK_KIND_ENCODING = {"slot": "fallback", "shape": "circle"}  # kinds beyond 8 (W113)
EXTENSION_RELATION_ENCODING = {"line": "solid", "arrow": "filled"}

_PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")
APP_SCRIPTS = ("graph-model.js", "graph-view.js", "pane.js", "app.js")  # in load order


def _vocabulary(ontology: Ontology) -> dict[str, list[dict[str, Any]]]:
    core, manifest = ontology.core, ontology.manifest
    kinds = [
        {"id": kid, "core": True, "status": "defined", **entry}
        for kid, entry in sorted(core.kinds.items(), key=lambda item: item[1]["encoding"]["slot"])
    ]
    extension_kinds = manifest.kind_extensions if manifest else {}
    for index, (kid, entry) in enumerate(sorted(extension_kinds.items())):
        encoding = (
            {"slot": 5 + index, "shape": EXTENSION_SHAPES[index]}
            if index < len(EXTENSION_SHAPES)
            else FALLBACK_KIND_ENCODING
        )
        kinds.append({"id": kid, "core": False, **entry, "encoding": encoding})

    relations = [{"id": rid, "core": True, "status": "defined", **entry} for rid, entry in core.relation_types.items()]
    extension_relations = manifest.relation_extensions if manifest else {}
    for rid, entry in sorted(extension_relations.items()):
        relations.append(
            {
                "id": rid,
                "core": False,
                "acyclic": False,
                "symmetric": False,
                **entry,
                "encoding": EXTENSION_RELATION_ENCODING,
            }
        )
    return {"kinds": kinds, "relation_types": relations}


def _concept(concept: Concept, root: Path, git: Git | None) -> dict[str, Any]:
    data = asdict(concept)
    data["file"] = concept.source.relative_to(root).as_posix()
    del data["source"]
    for impl in data["implemented_in"]:
        commit = impl["reviewed_at"]
        reachable = git is not None and commit is not None and git.is_reachable(commit)
        impl["reviewed_date"] = git.commit_date(commit) if reachable else None  # type: ignore[union-attr]
    return data


def _path_to_project(root: Path) -> str:
    """The relative URL prefix from the ontology folder to the project root (the working directory)."""
    up = Path(os.path.relpath(Path.cwd().resolve(), root.resolve())).as_posix()
    return "" if up == "." else up + "/"


def contract(ontology: Ontology, findings: list[Finding], git: Git | None, inputs: str) -> dict[str, Any]:
    manifest = ontology.manifest
    return {
        "schemaVersion": SCHEMA_VERSION,
        "skillVersion": skill_version(),
        "inputHash": inputs,
        "ontology": {
            "name": manifest.name if manifest else ontology.root.name,
            "description": manifest.description if manifest else "",
            "schema_version": manifest.schema_version if manifest else None,
            # From index.html's folder back to the project root, for implemented_in links.
            "path_to_project": _path_to_project(ontology.root),
        },
        "vocabulary": _vocabulary(ontology),
        "concepts": [_concept(c, ontology.root, git) for c in ontology.concepts.values()],
        "findings": [f.to_dict() for f in findings if f.code != "W108"],
    }


def _json_for_script(data: dict[str, Any]) -> str:
    """JSON that is safe inside <script>: no '<' (so no '</script>' or '<!--'), no JS line separators."""
    text = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=1)
    return text.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def _vendor_js() -> str:
    manifest = json.loads((VENDOR_DIR / "MANIFEST.json").read_text(encoding="utf-8"))
    licence = (VENDOR_DIR / manifest["license"]["file"]).read_text(encoding="utf-8").strip()
    modules = sorted(manifest["modules"], key=lambda m: m["order"])
    parts = [
        "/*! D3 modules: " + ", ".join(f"{m['module']} {m['version']}" for m in modules) + "\n"
        "https://d3js.org (ISC licence)\n\n" + licence + "\n*/"
    ]
    parts += [(VENDOR_DIR / m["file"]).read_text(encoding="utf-8").rstrip("\n") for m in modules]
    return "\n".join(parts)


def render(data: dict[str, Any]) -> str:
    template = (HTML_DIR / "index.html").read_text(encoding="utf-8")
    values = {
        "TITLE": html.escape(f"{data['ontology']['name']}: ontology"),
        "SKILL_VERSION": html.escape(data["skillVersion"]),
        "HASH_META": hash_meta(data["inputHash"]),
        "TOKENS_CSS": (HTML_DIR / "tokens.css").read_text(encoding="utf-8").strip(),
        "APP_CSS": (HTML_DIR / "app.css").read_text(encoding="utf-8").strip(),
        "DATA_JSON": _json_for_script(data),
        "VENDOR_JS": _vendor_js(),
        "APP_JS": "\n\n".join((HTML_DIR / name).read_text(encoding="utf-8").strip() for name in APP_SCRIPTS),
    }
    page = _PLACEHOLDER.sub(lambda m: values[m.group(1)], template)  # one pass: inserted text is never re-scanned
    return page.replace("\r\n", "\n")


def run(args: argparse.Namespace) -> int:
    root = Path(args.root)
    output = root / OUTPUT_FILE
    ctx = Context(git=Git.discover())
    try:
        ontology, load_findings = load(root)
    except OntologyUnavailable as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return EXIT_ENVIRONMENT
    inputs = input_hash(root)

    if args.check:
        if not output.is_file():
            sys.stderr.write(f"{display_path(output)} has not been built. Run 'onto.py build' and commit it.\n")
            return EXIT_FINDINGS
        if built_hash(output) != inputs:
            sys.stderr.write(
                f"{display_path(output)} is stale: the records changed since it was built. "
                "Run 'onto.py build' and commit the result.\n"
            )
            return EXIT_FINDINGS
        sys.stderr.write(f"{display_path(output)} is up to date.\n")
        return EXIT_OK

    findings = sort_findings([*load_findings, *run_checks(ontology, ctx)])
    page = render(contract(ontology, findings, ctx.git, inputs))
    for note in ctx.notes:
        if OUTPUT_FILE not in note:  # the "not built yet" note is about to be resolved
            sys.stderr.write(f"Note: {note}\n")

    relations = sum(len(c.relations) for c in ontology.concepts.values())
    errors = sum(f.severity == "error" for f in findings)
    summary = f"{len(ontology.concepts)} concepts, {relations} relations"
    if args.dry_run:
        sys.stderr.write(f"Would write {display_path(output)} ({len(page.encode('utf-8'))} bytes): {summary}.\n")
        return EXIT_OK
    output.write_bytes(page.encode("utf-8"))
    sys.stderr.write(f"Wrote {display_path(output)}: {summary}.\n")
    if errors:
        sys.stderr.write(
            f"The records have {errors} error{'s' if errors != 1 else ''}; the page lists them. "
            "Run 'onto.py validate' for details.\n"
        )
    return EXIT_OK
