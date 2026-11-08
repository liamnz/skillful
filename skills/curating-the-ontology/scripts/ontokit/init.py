"""The `init` command: scaffold docs/ontology/.

Idempotent: existing ontology files are never modified. Choices that need the user's
consent arrive as flags; without them, init changes nothing there and prints a hint:

- `--agents-md` writes the always-on pointer into AGENTS.md between marker comments,
  creating the file if needed. Re-running replaces only the marked section; the rest of
  the file stays byte-identical.
- `--gitattributes` adds one line marking index.html as generated, once.

Every planned change is checked before anything is written, so a refusal (for example
broken markers in AGENTS.md) leaves the project untouched.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from . import ASSETS_DIR
from .findings import EXIT_OK, EXIT_REFUSED
from .io import CONCEPTS_DIR, MANIFEST_FILE, display_path
from .staleness import OUTPUT_FILE

GITKEEP = ".gitkeep"
AGENTS_FILE = "AGENTS.md"
GITATTRIBUTES_FILE = ".gitattributes"
START = "<!-- curating-the-ontology:start"
END = "<!-- curating-the-ontology:end -->"


class Refused(Exception):
    pass


@dataclass
class Change:
    path: Path
    content: str
    created: bool
    bom: bool = False


def render_manifest(name: str) -> str:
    template = (ASSETS_DIR / "templates" / "ontology.yaml").read_text(encoding="utf-8")
    # A JSON string is a valid YAML double-quoted scalar, so any name is safe.
    return template.replace("{{name}}", json.dumps(name, ensure_ascii=False))


def _root_posix(root: Path) -> str:
    return display_path(root).rstrip("/")


def agents_section(root: Path) -> str:
    template = (ASSETS_DIR / "templates" / "agents-md-section.md").read_text(encoding="utf-8")
    return template.replace("{{root}}", _root_posix(root))


def _read(path: Path) -> tuple[str, bool]:
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    return raw.decode("utf-8-sig"), bom


def plan_agents_md(path: Path, root: Path) -> Change | None:
    """The new AGENTS.md text, or None if it is already up to date. Raises Refused."""
    section = agents_section(root)
    if not path.exists():
        return Change(path, section, created=True)
    text, bom = _read(path)
    eol = "\r\n" if "\r\n" in text else "\n"
    section = section.replace("\n", eol)
    starts, ends = text.count(START), text.count(END)
    if starts == 0 and ends == 0:
        # Append after one blank line.
        if not text or text.endswith(eol * 2):
            separator = ""
        elif text.endswith(eol):
            separator = eol
        else:
            separator = eol * 2
        return Change(path, text + separator + section, created=False, bom=bom)
    if starts != 1 or ends != 1 or text.index(START) > text.index(END):
        raise Refused(
            f"{display_path(path)} has {starts} start and {ends} end markers for the ontology section, so it "
            "can't be updated safely. Fix or remove the markers by hand, then re-run."
        )
    begin = text.index(START)
    finish = text.index(END) + len(END)
    if text[finish : finish + len(eol)] == eol:
        finish += len(eol)
    updated = text[:begin] + section + text[finish:]
    return None if updated == text else Change(path, updated, created=False, bom=bom)


def gitattributes_line(root: Path) -> str:
    return f"{_root_posix(root)}/{OUTPUT_FILE} -diff linguist-generated=true"


def plan_gitattributes(path: Path, root: Path) -> Change | None:
    line = gitattributes_line(root)
    if not path.exists():
        return Change(path, line + "\n", created=True)
    text, bom = _read(path)
    if any(existing.strip() == line for existing in text.splitlines()):
        return None
    eol = "\r\n" if "\r\n" in text else "\n"
    separator = "" if not text or text.endswith(("\n", "\r")) else eol
    return Change(path, text + separator + line + eol, created=False, bom=bom)


def _write(change: Change) -> None:
    change.path.parent.mkdir(parents=True, exist_ok=True)
    data = change.content.encode("utf-8")
    change.path.write_bytes((b"\xef\xbb\xbf" if change.bom else b"") + data)


def run(args: argparse.Namespace) -> int:
    root = Path(args.root)
    name = args.name or Path.cwd().name
    planned: list[tuple[Path, str]] = [
        (root / MANIFEST_FILE, render_manifest(name)),
        (root / CONCEPTS_DIR / GITKEEP, ""),
    ]

    # Plan the consented edits first: a refusal must leave everything untouched.
    try:
        agents = plan_agents_md(Path(AGENTS_FILE), root) if args.agents_md else None
    except Refused as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return EXIT_REFUSED
    attributes = plan_gitattributes(Path(GITATTRIBUTES_FILE), root) if args.gitattributes else None

    verb = "would create" if args.dry_run else "created"
    for path, content in planned:
        if path.exists():
            sys.stderr.write(f"{display_path(path)} already exists; left unchanged.\n")
            if path.name == MANIFEST_FILE and args.name:
                sys.stderr.write("  --name was not applied; edit `name` in the manifest to change it.\n")
            continue
        if not args.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
        print(f"{verb} {display_path(path)}")

    for flag, target, change, what in (
        (args.agents_md, AGENTS_FILE, agents, "the ontology section"),
        (args.gitattributes, GITATTRIBUTES_FILE, attributes, "the index.html line"),
    ):
        if not flag:
            continue
        if change is None:
            sys.stderr.write(f"{target} already has {what}; left unchanged.\n")
            continue
        action = (
            ("create" if change.created else "update") if args.dry_run else ("created" if change.created else "updated")
        )
        if args.dry_run:
            print(f"would {action} {target} ({what})")
        else:
            _write(change)
            print(f"{action} {target} ({what})")

    if args.agents_md is None:
        sys.stderr.write(
            "Hint: AGENTS.md was not changed. Ask the user whether to add the always-on pointer "
            "to the ontology, then re-run with --agents-md or --no-agents-md.\n"
        )
    if args.gitattributes is None:
        sys.stderr.write(
            "Hint: .gitattributes was not changed. Ask the user whether to mark index.html as generated "
            "(hides it from diffs and PR reviews), then re-run with --gitattributes or --no-gitattributes.\n"
        )
    return EXIT_OK
