"""Vocabulary extensions: their checks and the `vocab new` / `vocab list` commands.

Extensions are governed like concepts. `vocab new` only ever adds a `proposed`
extension with the agent's rationale; definitions and `defined` belong to humans.

Checks: E005 unknown kind or relation type, E010 reused id, E011 defined without a
definition, E012 unknown kind in from/to, W110 from/to broken, W112 deprecated
extension in use, W113 more than 8 kinds in use, I203 declared but unused.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

from .context import Context
from .findings import EXIT_ENVIRONMENT, EXIT_OK, EXIT_REFUSED, EXIT_USAGE, Finding, finding
from .io import MANIFEST_FILE, Ontology, OntologyNotFound, display_path, load
from .schema import schema_errors

ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
MAX_DISTINCT_KINDS = 8  # the graph has 8 kind colour slots (see tokens.css)
SECTIONS = {"kind": "kinds", "relation": "relation_types"}


# --- Checks ---------------------------------------------------------------------------


def check_vocabulary(ontology: Ontology, ctx: Context) -> Iterator[Finding]:
    yield from _unknown_terms(ontology)
    yield from _reused_ids(ontology)
    yield from _extension_definitions(ontology)
    yield from _constraints(ontology)
    yield from _deprecated_in_use(ontology)
    yield from _usage(ontology)


def _unknown_terms(ontology: Ontology) -> Iterator[Finding]:
    """E005: a concept's kind or a relation's type that is neither core nor declared.

    Skipped while the manifest is invalid (E001/E002): its extensions are unknown, not undeclared.
    """
    if ontology.manifest is None:
        return
    kinds, types = ontology.kinds, ontology.relation_types
    for concept in ontology.concepts.values():
        if concept.kind not in kinds:
            yield finding(
                "E005",
                concept.id,
                f"Kind '{concept.kind}' is neither core nor a declared extension. Use one of: "
                f"{', '.join(kinds)}; or propose it with 'onto.py vocab new kind {concept.kind} --rationale ...'.",
            )
        for relation_type in sorted({r.type for r in concept.relations if r.type not in types}):
            yield finding(
                "E005",
                concept.id,
                f"Relation type '{relation_type}' is neither core nor a declared extension. Use one of: "
                f"{', '.join(types)}; or propose it with 'onto.py vocab new relation {relation_type} ...'.",
            )


def _duplicate_keys(path: Path) -> list[tuple[str, str]]:
    """(section, id) for every extension id written twice in the manifest (YAML keeps only the last)."""
    try:
        root = yaml.compose(path.read_text(encoding="utf-8-sig"))
    except (yaml.YAMLError, UnicodeDecodeError, OSError):
        return []  # E001 already reports it
    duplicates: list[tuple[str, str]] = []

    def child(node: Any, key: str) -> Any:
        if isinstance(node, yaml.MappingNode):
            return next((v for k, v in node.value if getattr(k, "value", None) == key), None)
        return None

    extensions = child(root, "extensions")
    for section in SECTIONS.values():
        node = child(extensions, section)
        if isinstance(node, yaml.MappingNode):
            counts = Counter(k.value for k, _ in node.value if isinstance(k, yaml.ScalarNode))
            duplicates += [(section, key) for key, n in sorted(counts.items()) if n > 1]
    return duplicates


def _reused_ids(ontology: Ontology) -> Iterator[Finding]:
    """E010: an extension reuses a core id, or two extensions share an id."""
    manifest = ontology.manifest
    if manifest is None:
        return
    core_ids = {*ontology.core.kinds, *ontology.core.relation_types}
    declared = {"kinds": manifest.kind_extensions, "relation_types": manifest.relation_extensions}
    for section, extensions in declared.items():
        for ext_id in extensions:
            if ext_id in core_ids:
                yield finding(
                    "E010",
                    None,
                    f"extensions.{section}.{ext_id} reuses the core id '{ext_id}', whose meaning is fixed. "
                    "Choose another id for the extension.",
                )
    for ext_id in sorted(set(manifest.kind_extensions) & set(manifest.relation_extensions)):
        yield finding(
            "E010",
            None,
            f"'{ext_id}' is declared both as a kind and as a relation type. Give one of them another id.",
        )
    for section, ext_id in _duplicate_keys(manifest.source):
        yield finding(
            "E010",
            None,
            f"extensions.{section}.{ext_id} is declared more than once; only the last one takes effect. "
            "Merge them into one entry.",
        )


def _extension_definitions(ontology: Ontology) -> Iterator[Finding]:
    """E011: a `defined` extension without a definition."""
    manifest = ontology.manifest
    if manifest is None:
        return
    for section, extensions in (("kinds", manifest.kind_extensions), ("relation_types", manifest.relation_extensions)):
        for ext_id, entry in extensions.items():
            if entry.get("status") == "defined" and not (entry.get("definition") or "").strip():
                yield finding(
                    "E011",
                    None,
                    f"extensions.{section}.{ext_id} is defined but has no definition. A human writes it; "
                    "until then set status back to proposed.",
                )


def _constraints(ontology: Ontology) -> Iterator[Finding]:
    """E012 from/to names an unknown kind; W110 a relation breaks its type's from/to."""
    kinds = ontology.kinds
    manifest = ontology.manifest
    if manifest is not None:
        for ext_id, entry in manifest.relation_extensions.items():
            for side in ("from", "to"):
                for kind in entry.get(side) or ():
                    if kind not in kinds:
                        yield finding(
                            "E012",
                            None,
                            f"extensions.relation_types.{ext_id}.{side} names '{kind}', which is not a kind. "
                            f"Use one of: {', '.join(kinds)}.",
                        )
    types = ontology.relation_types
    concepts = ontology.concepts
    for concept in concepts.values():
        for relation in concept.relations:
            spec = types.get(relation.type)
            target = concepts.get(relation.target)
            if spec is None or target is None:
                continue
            for side, kind in (("from", concept.kind), ("to", target.kind)):
                allowed = spec.get(side)
                if allowed and kind in kinds and kind not in allowed:
                    role = "source" if side == "from" else "target"
                    yield finding(
                        "W110",
                        concept.id,
                        f"'{relation.type}' to '{target.id}' has a {role} of kind '{kind}', but '{relation.type}' "
                        f"only allows {role}s of kind {', '.join(allowed)}. Check the kinds, or use another "
                        "relation type.",
                    )


def _deprecated_in_use(ontology: Ontology) -> Iterator[Finding]:
    """W112: a concept or relation uses a deprecated extension."""
    manifest = ontology.manifest
    if manifest is None:
        return
    deprecated_kinds = {k for k, e in manifest.kind_extensions.items() if e.get("status") == "deprecated"}
    deprecated_types = {k for k, e in manifest.relation_extensions.items() if e.get("status") == "deprecated"}
    for concept in ontology.concepts.values():
        if concept.status == "deprecated":
            continue
        if concept.kind in deprecated_kinds:
            yield finding(
                "W112",
                concept.id,
                f"Kind '{concept.kind}' is deprecated. Move the concept to another kind.",
            )
        for relation_type in sorted({r.type for r in concept.relations} & deprecated_types):
            yield finding(
                "W112",
                concept.id,
                f"Relation type '{relation_type}' is deprecated. Restate the relation with another type.",
            )


def usage_counts(ontology: Ontology) -> tuple[Counter[str], Counter[str]]:
    """How many concepts use each kind, and how many relations use each relation type."""
    kinds = Counter(c.kind for c in ontology.concepts.values())
    types = Counter(r.type for c in ontology.concepts.values() for r in c.relations)
    return kinds, types


def _usage(ontology: Ontology) -> Iterator[Finding]:
    """W113 too many kinds in use; I203 an extension nothing uses."""
    kinds_used, types_used = usage_counts(ontology)
    in_use = sorted(k for k in kinds_used if k in ontology.kinds)
    if len(in_use) > MAX_DISTINCT_KINDS:
        yield finding(
            "W113",
            None,
            f"{len(in_use)} kinds are in use ({', '.join(in_use)}), but the graph can only show "
            f"{MAX_DISTINCT_KINDS} distinctly; the rest share a neutral colour. Merge or retire kinds.",
        )
    manifest = ontology.manifest
    if manifest is None:
        return
    for section, extensions, used in (
        ("kinds", manifest.kind_extensions, kinds_used),
        ("relation_types", manifest.relation_extensions, types_used),
    ):
        for ext_id, entry in extensions.items():
            if not used[ext_id] and entry.get("status") != "deprecated":
                yield finding(
                    "I203",
                    None,
                    f"extensions.{section}.{ext_id} is declared but nothing uses it. Is it needed?",
                )


# --- vocab list -------------------------------------------------------------------------


def vocabulary_rows(ontology: Ontology) -> list[dict[str, Any]]:
    """Core then extension kinds, then core then extension relation types, with usage counts."""
    kinds_used, types_used = usage_counts(ontology)
    manifest = ontology.manifest
    rows: list[dict[str, Any]] = []
    for kind_id, entry in ontology.core.kinds.items():
        rows.append(_row("kind", kind_id, entry, True, kinds_used[kind_id]))
    for kind_id, entry in (manifest.kind_extensions if manifest else {}).items():
        rows.append(_row("kind", kind_id, entry, False, kinds_used[kind_id]))
    for type_id, entry in ontology.core.relation_types.items():
        rows.append(_row("relation", type_id, entry, True, types_used[type_id]))
    for type_id, entry in (manifest.relation_extensions if manifest else {}).items():
        rows.append(_row("relation", type_id, entry, False, types_used[type_id]))
    return rows


def _row(vocab_type: str, vocab_id: str, entry: dict[str, Any], core: bool, used: int) -> dict[str, Any]:
    row: dict[str, Any] = {
        "type": vocab_type,
        "id": vocab_id,
        "core": core,
        "status": "defined" if core else entry.get("status"),
        "definition": " ".join((entry.get("definition") or "").split()),
        "usage": used,
    }
    if vocab_type == "relation":
        row |= {
            "inverse": entry.get("inverse"),
            "acyclic": bool(entry.get("acyclic", False)),
            "from": list(entry.get("from") or []),
            "to": list(entry.get("to") or []),
        }
    return row


def run_list(args: argparse.Namespace) -> int:
    try:
        ontology, _ = load(Path(args.root))
    except OntologyNotFound as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return EXIT_ENVIRONMENT
    rows = vocabulary_rows(ontology)
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return EXIT_OK
    for row in rows:
        origin = "core" if row["core"] else "extension"
        detail = ""
        if row["type"] == "relation":
            limits = [f"{side} {', '.join(row[side])}" for side in ("from", "to") if row[side]]
            detail = f"  inverse {row['inverse']}" + ("  acyclic" if row["acyclic"] else "")
            detail += "".join(f"  {limit}" for limit in limits)
        print(f"{row['type']:<8}  {row['id']:<16}  {origin:<9}  {row['status']:<10}  used {row['usage']}{detail}")
    sys.stderr.write(
        f"{sum(r['type'] == 'kind' for r in rows)} kinds, {sum(r['type'] == 'relation' for r in rows)} "
        "relation types.\n"
    )
    return EXIT_OK


# --- vocab new --------------------------------------------------------------------------


class Refused(Exception):
    pass


class UsageError(Exception):
    pass


def render_entry(vocab_type: str, ext_id: str, args: argparse.Namespace, indent: str, eol: str) -> str:
    """The YAML lines for one proposed extension, at `indent` (the section's child indent)."""
    step = "  "
    lines = [f"{ext_id}:", f"{step}status: proposed", f'{step}definition: ""  # HUMAN-AUTHORED']
    if vocab_type == "relation":
        lines.append(f"{step}inverse: {args.inverse}")
        if args.acyclic:
            lines.append(f"{step}acyclic: true")
        if args.from_kinds:
            lines.append(f"{step}from: [{', '.join(args.from_kinds)}]")
        if args.to_kinds:
            lines.append(f"{step}to: [{', '.join(args.to_kinds)}]")
    lines += [
        f"{step}proposal:  # AGENT-AUTHORED; remove once the extension is defined",
        f"{step}{step}rationale: {json.dumps(args.rationale.strip(), ensure_ascii=False)}",
    ]
    return "".join(f"{indent}{line}{eol}" for line in lines)


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _key_line(lines: list[str], key: str, start: int, end: int, indent: int | None) -> int | None:
    pattern = re.compile(r"^( *)" + re.escape(key) + r":(.*)$")
    for i in range(start, end):
        match = pattern.match(lines[i].rstrip("\r\n"))
        if match and (indent is None or len(match.group(1)) == indent):
            return i
    return None


def _block_end(lines: list[str], start: int, parent_indent: int) -> int:
    """Index just after the block under lines[start]: children are indented deeper than the parent.

    Blank lines and deeper-indented comments belong to the block; trailing blank lines do not.
    """
    end = start + 1
    last = start + 1
    while end < len(lines):
        text = lines[end].rstrip("\r\n")
        if text.strip() and _indent(text) <= parent_indent:
            break
        end += 1
        if text.strip():
            last = end
    return last


def insert_extension(text: str, section: str, entry_for: Any) -> str:
    """Insert one entry at the end of extensions.<section>, creating keys as needed. Rest is unchanged."""
    eol = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith(("\n", "\r")):
        lines[-1] += eol

    ext = _key_line(lines, "extensions", 0, len(lines), 0)
    if ext is None:
        settings = _key_line(lines, "settings", 0, len(lines), 0)
        at = settings if settings is not None else len(lines)
        block = f"extensions:{eol}  {section}:{eol}" + entry_for("    ", eol)
        if settings is not None:
            block += eol
        return "".join(lines[:at]) + block + "".join(lines[at:])

    _check_inline(lines[ext], "extensions")
    lines[ext] = _open_block(lines[ext], eol)
    ext_end = _block_end(lines, ext, 0)
    sec = _key_line(lines, section, ext + 1, ext_end, None)
    if sec is None:
        child = next(
            (
                _indent(lines[i])
                for i in range(ext + 1, ext_end)
                if lines[i].strip() and not lines[i].lstrip().startswith("#")
            ),
            2,
        )
        block = f"{' ' * child}{section}:{eol}" + entry_for(" " * (child * 2), eol)
        return "".join(lines[:ext_end]) + block + "".join(lines[ext_end:])

    indent = _indent(lines[sec])
    _check_inline(lines[sec], section)
    lines[sec] = _open_block(lines[sec], eol)
    sec_end = _block_end(lines, sec, indent)
    entries = [i for i in range(sec + 1, sec_end) if lines[i].strip() and not lines[i].lstrip().startswith("#")]
    child = _indent(lines[entries[0]]) if entries else indent + 2
    return "".join(lines[:sec_end]) + entry_for(" " * child, eol) + "".join(lines[sec_end:])


def _open_block(line: str, eol: str) -> str:
    """`key: {}` or `key: null` becomes `key:`, ready for children. Other lines are unchanged."""
    text = line.rstrip("\r\n")
    opened = re.sub(r":\s*(\{\}|null|~)\s*(#.*)?$", ":", text)
    return line if opened == text else opened + eol


def _check_inline(line: str, key: str) -> None:
    """Refuse a flow-style value such as `kinds: {rule: {...}}`: it can't be extended line by line."""
    value = line.split(":", 1)[1].split("#", 1)[0].strip()
    if value not in ("", "{}", "null", "~"):
        raise Refused(
            f"'{key}' in {MANIFEST_FILE} is written inline ('{value}'), so it can't be extended safely. "
            "Rewrite it in block style, one key per line, and re-run."
        )


def _check_new(args: argparse.Namespace, vocab_type: str, ontology: Ontology) -> None:
    if not ID_PATTERN.match(args.id):
        raise UsageError(
            f'id must be snake_case (a lowercase letter, then lowercase letters, digits or "_"). Received: "{args.id}".'
        )
    if not args.rationale.strip():
        raise UsageError("--rationale must say why no existing vocabulary fits.")
    core = {*ontology.core.kinds, *ontology.core.relation_types}
    if args.id in core:
        raise Refused(f"'{args.id}' is core vocabulary; its meaning is fixed and can't be redefined.")
    manifest = ontology.manifest
    existing = {*manifest.kind_extensions, *manifest.relation_extensions} if manifest else set()
    if args.id in existing:
        raise Refused(
            f"'{args.id}' is already declared in {MANIFEST_FILE}. Edit that entry instead; "
            "'vocab new' never changes an existing one."
        )
    if vocab_type == "relation":
        if not ID_PATTERN.match(args.inverse):
            raise UsageError(f'--inverse must be snake_case. Received: "{args.inverse}".')
        kinds = list(ontology.kinds)
        for kind in [*args.from_kinds, *args.to_kinds]:
            if kind not in kinds:
                raise UsageError(
                    f'--from/--to must name kinds: {", ".join(kinds)}. Received: "{kind}". '
                    'Run "onto.py vocab list" to see all kinds.'
                )


def run_new(args: argparse.Namespace) -> int:
    vocab_type = args.vocab_new_type
    root = Path(args.root)
    try:
        ontology, findings = load(root)
    except OntologyNotFound as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return EXIT_ENVIRONMENT
    if ontology.manifest is None:
        sys.stderr.write(
            f"Error: {MANIFEST_FILE} is invalid ({findings[0].message}). Fix it with 'onto.py validate' first.\n"
        )
        return EXIT_ENVIRONMENT
    try:
        _check_new(args, vocab_type, ontology)
        path = ontology.manifest.source
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
        section = SECTIONS[vocab_type]
        updated = insert_extension(
            text, section, lambda indent, eol: render_entry(vocab_type, args.id, args, indent, eol)
        )
    except UsageError as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return EXIT_USAGE
    except Refused as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return EXIT_REFUSED

    data = yaml.safe_load(updated)
    entry = ((data.get("extensions") or {}).get(section) or {}).get(args.id)
    errors = schema_errors("manifest", data)
    if entry is None or entry.get("status") != "proposed" or errors:
        sys.stderr.write(
            f"Error: could not add '{args.id}' to {display_path(path)} safely; the file was not changed. "
            "Add it by hand under extensions.\n"
        )
        return EXIT_REFUSED

    added = render_entry(vocab_type, args.id, args, "", "\n")
    if args.dry_run:
        sys.stdout.write(added)
        sys.stderr.write(f"Dry run: would add the {vocab_type} '{args.id}' to {display_path(path)}.\n")
        return EXIT_OK
    bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    path.write_bytes(bom + updated.encode("utf-8"))
    print(f"added proposed {vocab_type} '{args.id}' to {display_path(path)}")
    sys.stderr.write("Next: ask the human to write the definition in their own words, then set status: defined.\n")
    return EXIT_OK
