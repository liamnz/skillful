"""The `new` command: create a status=proposed concept stub.

There is deliberately no way to set another status or a definition: definitions and
promotion to `defined` belong to humans.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath

import yaml

from .findings import EXIT_ENVIRONMENT, EXIT_OK, EXIT_REFUSED, EXIT_USAGE
from .io import CONCEPTS_DIR, OntologyUnavailable, display_path, load
from .schema import schema_errors

ID_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")


class UsageError(Exception):
    pass


def _quote(value: str) -> str:
    # A JSON string is a valid YAML double-quoted scalar.
    return json.dumps(value, ensure_ascii=False)


def parse_implemented_in(spec: str) -> dict[str, str]:
    """Parse 'path[:symbol]' into a repo-relative POSIX path and an optional symbol."""
    if _DRIVE.match(spec) or spec.startswith(("/", "\\")):
        raise UsageError(f'--implemented-in must be a repo-relative path. Received: "{spec}".')
    path, sep, symbol = spec.rpartition(":")
    if not sep:
        path, symbol = spec, ""
    elif not symbol:
        raise UsageError(f'--implemented-in has an empty symbol after ":". Received: "{spec}".')
    parts = [p for p in PurePosixPath(path.replace("\\", "/")).parts if p != "."]
    if not parts or ".." in parts:
        raise UsageError(f'--implemented-in must point inside the repository. Received: "{spec}".')
    entry = {"path": "/".join(parts)}
    if symbol:
        entry["symbol"] = symbol
    return entry


def render_concept(
    concept_id: str,
    name: str,
    kind: str,
    rationale: str | None,
    suggestion: str | None,
    implemented_in: list[dict[str, str]],
) -> str:
    lines = [
        f"id: {concept_id}",
        f"name: {_quote(name)}",
        f"kind: {kind}",
        "status: proposed",
        'definition: ""  # HUMAN-AUTHORED: write it in your own words, then set status: defined',
        "relations: []",
    ]
    if implemented_in:
        lines.append("implemented_in:")
        for entry in implemented_in:
            lines.append(f"  - path: {_quote(entry['path'])}")
            if "symbol" in entry:
                lines.append(f"    symbol: {_quote(entry['symbol'])}")
    if rationale or suggestion:
        lines.append("proposal:  # AGENT-AUTHORED; remove once the concept is defined")
        if rationale:
            lines.append(f"  rationale: {_quote(rationale)}")
        if suggestion:
            lines.append(f"  suggested_definition: {_quote(suggestion)}")
    return "\n".join(lines) + "\n"


def _check_args(args: argparse.Namespace, valid_kinds: list[str]) -> list[dict[str, str]]:
    if not ID_PATTERN.match(args.id):
        raise UsageError(
            f'id must be kebab-case (lowercase letters and digits joined by single hyphens). Received: "{args.id}".'
        )
    if not args.name.strip():
        raise UsageError("--name must not be empty.")
    if args.kind not in valid_kinds:
        raise UsageError(
            f'--kind must be one of: {", ".join(valid_kinds)}. Received: "{args.kind}". '
            'Run "onto.py vocab list" to see all kinds.'
        )
    return [parse_implemented_in(spec) for spec in args.implemented_in]


def run(args: argparse.Namespace) -> int:
    root = Path(args.root)
    try:
        ontology, _ = load(root)
    except OntologyUnavailable as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return EXIT_ENVIRONMENT

    declared = list(ontology.manifest.kind_extensions) if ontology.manifest else []
    valid_kinds = [*ontology.core.kinds, *declared]
    try:
        implemented_in = _check_args(args, valid_kinds)
    except UsageError as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return EXIT_USAGE

    path = root / CONCEPTS_DIR / f"{args.id}.yaml"
    if path.exists():
        sys.stderr.write(
            f"Error: {display_path(path)} already exists; new never overwrites a concept. "
            "Choose another id, or edit the existing record.\n"
        )
        return EXIT_REFUSED

    text = render_concept(
        args.id, args.name.strip(), args.kind, args.rationale, args.suggested_definition, implemented_in
    )
    errors = schema_errors("concept", yaml.safe_load(text))
    assert not errors, f"rendered concept failed its own schema: {errors}"

    for entry in implemented_in:
        if not Path(entry["path"]).exists():
            sys.stderr.write(f"Warning: {entry['path']} does not exist (relative to {Path.cwd().as_posix()}).\n")

    if args.dry_run:
        sys.stdout.write(text)
        sys.stderr.write(f"Dry run: would create {display_path(path)}.\n")
        return EXIT_OK

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print(f"created {display_path(path)}")
    sys.stderr.write(
        "Next: ask the human to write the definition in their own words, "
        "then set status: defined. Rebuild the view with 'onto.py build'.\n"
    )
    return EXIT_OK
