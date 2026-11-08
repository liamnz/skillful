"""The `review` command: record that a human confirmed a definition still matches the code.

Sets `reviewed_at` to HEAD on the concept's `implemented_in` entries. The record is
edited in place as text, using YAML node positions, so comments, formatting and line
endings written by humans are preserved. The result is re-parsed and checked before
anything is written.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from .findings import EXIT_ENVIRONMENT, EXIT_OK, EXIT_REFUSED
from .gitinfo import Git
from .io import CONCEPTS_DIR, OntologyNotFound, display_path, load
from .schema import schema_errors

BOM = "﻿"


class EditError(Exception):
    pass


@dataclass(frozen=True)
class _Edit:
    start: int
    end: int
    text: str


def _value(mapping: MappingNode, key: str) -> Node | None:
    for key_node, value_node in mapping.value:
        if isinstance(key_node, ScalarNode) and key_node.value == key:
            return value_node
    return None


def _edit_for_entry(text: str, entry: MappingNode, commit: str, newline: str) -> _Edit:
    existing = _value(entry, "reviewed_at")
    if existing is not None:
        return _Edit(existing.start_mark.index, existing.end_mark.index, commit)
    if entry.flow_style:
        # `{path: x, symbol: y}` -> `{path: x, symbol: y, reviewed_at: <commit>}`
        close = text.rindex("}", entry.start_mark.index, entry.end_mark.index)
        return _Edit(close, close, f", reviewed_at: {commit}")
    indent = " " * entry.value[0][0].start_mark.column
    last_value = entry.value[-1][1]
    index = last_value.end_mark.index
    if index > 0 and text[index - 1] == "\n":
        insert_at = index  # value ended with a line break (e.g. a block scalar)
    else:
        line_end = text.find("\n", index)
        insert_at = len(text) if line_end == -1 else line_end + 1
        if line_end == -1:
            return _Edit(insert_at, insert_at, f"{newline}{indent}reviewed_at: {commit}{newline}")
    return _Edit(insert_at, insert_at, f"{indent}reviewed_at: {commit}{newline}")


def set_reviewed_at(text: str, paths: set[str], commit: str) -> str:
    """Return `text` with reviewed_at set to `commit` on the implemented_in entries for `paths`."""
    newline = "\r\n" if "\r\n" in text else "\n"
    root = yaml.compose(text)
    if not isinstance(root, MappingNode):
        raise EditError("the record is not a YAML mapping")
    entries = _value(root, "implemented_in")
    if not isinstance(entries, SequenceNode):
        raise EditError("the record has no implemented_in list")

    edits = []
    for entry in entries.value:
        path_node = _value(entry, "path") if isinstance(entry, MappingNode) else None
        if isinstance(path_node, ScalarNode) and path_node.value in paths:
            edits.append(_edit_for_entry(text, entry, commit, newline))  # type: ignore[arg-type]
    for edit in sorted(edits, key=lambda e: e.start, reverse=True):
        text = text[: edit.start] + edit.text + text[edit.end :]
    return text


def _verify(before: str, after: str, paths: set[str], commit: str) -> None:
    old, new = yaml.safe_load(before), yaml.safe_load(after)
    errors = schema_errors("concept", new)
    if errors:
        raise EditError(f"the edited record would violate the schema: {errors}")
    for entry in new["implemented_in"]:
        if entry["path"] in paths and entry.get("reviewed_at") != commit:
            raise EditError(f"reviewed_at was not set for {entry['path']}")
    strip = [{k: v for k, v in e.items() if k != "reviewed_at"} for e in new["implemented_in"]]
    if {**new, "implemented_in": strip} != {
        **old,
        "implemented_in": [{k: v for k, v in e.items() if k != "reviewed_at"} for e in old["implemented_in"]],
    }:
        raise EditError("the edit changed more than reviewed_at")
    untouched_old = [e.get("reviewed_at") for e in old["implemented_in"] if e["path"] not in paths]
    untouched_new = [e.get("reviewed_at") for e in new["implemented_in"] if e["path"] not in paths]
    if untouched_old != untouched_new:
        raise EditError("the edit changed reviewed_at on an entry that was not being reviewed")


def _refuse(message: str) -> int:
    sys.stderr.write(f"Error: {message}\n")
    return EXIT_REFUSED


def run(args: argparse.Namespace) -> int:
    git = Git.discover()
    if git is None:
        sys.stderr.write(
            "Error: review needs a git repository with at least one commit, because it records the "
            "commit (HEAD) at which the definition was confirmed. Run it from the project root.\n"
        )
        return EXIT_ENVIRONMENT
    root = Path(args.root)
    try:
        ontology, _ = load(root)
    except OntologyNotFound as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return EXIT_ENVIRONMENT

    concept = ontology.concepts.get(args.id)
    if concept is None:
        return _refuse(
            f"no valid concept '{args.id}' (concepts/{args.id}.yaml is missing or invalid). "
            "Run 'onto.py validate' to see why."
        )
    if concept.status == "proposed":
        return _refuse(
            f"'{args.id}' is still proposed, so it has no confirmed definition to review. "
            "A human writes the definition and sets status: defined first."
        )
    if not concept.implemented_in:
        return _refuse(f"'{args.id}' has no implemented_in entries, so there is no code to review it against.")

    known = [i.path for i in concept.implemented_in]
    if args.path is not None:
        wanted = args.path.replace("\\", "/").removeprefix("./")
        if wanted not in known:
            return _refuse(f"'{args.id}' has no implemented_in path '{args.path}'. Its paths are: {', '.join(known)}.")
        paths = {wanted}
    else:
        paths = set(known)

    dirty = sorted(p for p in paths if git.has_uncommitted_changes(p))
    if dirty:
        return _refuse(
            f"uncommitted changes in {', '.join(dirty)}. A review is recorded against a commit, so "
            "commit the code first, then run review again (otherwise the change would count as drift "
            "as soon as it is committed)."
        )

    head = git.head()
    assert head is not None
    path = root / CONCEPTS_DIR / f"{args.id}.yaml"
    raw = path.read_bytes().decode("utf-8")
    bom = raw.startswith(BOM)
    before = raw.removeprefix(BOM)
    try:
        after = set_reviewed_at(before, paths, head)
        _verify(before, after, paths, head)
    except (EditError, yaml.YAMLError) as exc:
        sys.stderr.write(f"Error: could not edit {display_path(path)} safely: {exc}. Nothing was written.\n")
        return EXIT_REFUSED

    summary = ", ".join(sorted(paths))
    if args.dry_run:
        sys.stderr.write(f"Dry run: would set reviewed_at to {git.short(head)} for {args.id}: {summary}\n")
        return EXIT_OK
    path.write_bytes(((BOM if bom else "") + after).encode("utf-8"))
    print(f"reviewed {args.id} at {git.short(head)}: {summary}")
    return EXIT_OK
