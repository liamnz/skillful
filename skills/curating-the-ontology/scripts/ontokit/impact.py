"""The `impact` command: concepts touched by changed files, and changed files mapped to no concept.

Changed files are those committed since the merge-base with the base (default: the
repository's default branch), plus staged, unstaged and untracked files. Files under
the ontology directory itself are left out: they are the records, not the code.

Deciding whether an unmapped file introduces a domain concept is the agent's job.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .drift import git_path
from .findings import EXIT_ENVIRONMENT, EXIT_OK
from .gitinfo import Git
from .io import Ontology, OntologyUnavailable, load


def impact(ontology: Ontology, changed: list[str]) -> dict[str, Any]:
    """The impact report for a list of changed paths (relative to the project root)."""
    ontology_dir = git_path(ontology.root).rstrip("/") + "/"
    code = [p for p in changed if not (p + "/").startswith(ontology_dir) and p != ontology_dir.rstrip("/")]
    referenced: dict[str, list[str]] = {}
    for concept in ontology.concepts.values():
        for impl in concept.implemented_in:
            path = Path(impl.path).as_posix()
            referenced.setdefault(path, [])
            if concept.id not in referenced[path]:
                referenced[path].append(concept.id)

    files = [{"path": p, "concepts": sorted(referenced.get(p, []))} for p in code]
    concepts: dict[str, list[str]] = {}
    for entry in files:
        for concept_id in entry["concepts"]:
            concepts.setdefault(concept_id, []).append(entry["path"])
    return {
        "changed_files": files,
        "concepts": [{"id": c, "paths": paths} for c, paths in sorted(concepts.items())],
        "unmapped_files": [entry["path"] for entry in files if not entry["concepts"]],
    }


def _limited(report: dict[str, Any], limit: int | None) -> tuple[dict[str, Any], list[str]]:
    if limit is None:
        return report, []
    notes = []
    out = {}
    for key, items in report.items():
        out[key] = items[:limit] if isinstance(items, list) else items
        if isinstance(items, list) and len(items) > limit:
            notes.append(f"{key}: showing {limit} of {len(items)}")
    return out, notes


def run(args: argparse.Namespace) -> int:
    git = Git.discover()
    if git is None:
        sys.stderr.write("Error: impact needs a git repository with at least one commit. Run it from the repo root.\n")
        return EXIT_ENVIRONMENT
    try:
        ontology, _ = load(Path(args.root))
    except OntologyUnavailable as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return EXIT_ENVIRONMENT

    base = args.base
    if base is None:
        base = git.default_branch()
        if base is None:
            sys.stderr.write(
                "Error: could not tell the default branch (no origin/HEAD, and no local main or master). "
                "Pass the branch to compare against, e.g. --base develop.\n"
            )
            return EXIT_ENVIRONMENT
    if not git.ref_exists(base):
        sys.stderr.write(f"Error: --base '{base}' is not a commit or branch in this repository.\n")
        return EXIT_ENVIRONMENT
    merge_base = git.merge_base(base)
    if merge_base is None:
        sys.stderr.write(f"Error: '{base}' shares no history with HEAD, so there is no merge-base to compare with.\n")
        return EXIT_ENVIRONMENT

    report, notes = _limited(impact(ontology, git.changed_files(merge_base)), args.limit)
    if args.json:
        print(json.dumps({"base": base, **report}, indent=2, ensure_ascii=False))
    else:
        _print_human(report)
    sys.stderr.write(
        f"Compared with {base} (merge-base {git.short(merge_base)}), including uncommitted and untracked files.\n"
    )
    for note in notes:
        sys.stderr.write(f"Limited by --limit {args.limit}: {note}.\n")
    return EXIT_OK


def _print_human(report: dict[str, Any]) -> None:
    concepts = report["concepts"]
    unmapped = report["unmapped_files"]
    if not report["changed_files"]:
        print("No changed files.")
        return
    print("Concepts whose code changed (review these definitions):" if concepts else "No concept's code changed.")
    for entry in concepts:
        print(f"  {entry['id']}: {', '.join(entry['paths'])}")
    print(
        "Changed files mapped to no concept (possible new concepts):" if unmapped else "Every changed file is mapped."
    )
    for path in unmapped:
        print(f"  {path}")
