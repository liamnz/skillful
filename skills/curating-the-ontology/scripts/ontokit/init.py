"""The `init` command: scaffold docs/ontology/.

Idempotent: existing files are never modified. Choices that need the user's consent
(AGENTS.md, .gitattributes) arrive as flags; without them, init only prints a hint.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import ASSETS_DIR
from .findings import EXIT_OK, EXIT_USAGE
from .io import CONCEPTS_DIR, MANIFEST_FILE, display_path

GITKEEP = ".gitkeep"


def render_manifest(name: str) -> str:
    template = (ASSETS_DIR / "templates" / "ontology.yaml").read_text(encoding="utf-8")
    # A JSON string is a valid YAML double-quoted scalar, so any name is safe.
    return template.replace("{{name}}", json.dumps(name, ensure_ascii=False))


def run(args: argparse.Namespace) -> int:
    if args.agents_md or args.gitattributes:
        flag = "--agents-md" if args.agents_md else "--gitattributes"
        sys.stderr.write(f"Error: {flag} is not implemented yet. Re-run without it.\n")
        return EXIT_USAGE

    root = Path(args.root)
    name = args.name or Path.cwd().name
    planned: list[tuple[Path, str]] = [
        (root / MANIFEST_FILE, render_manifest(name)),
        (root / CONCEPTS_DIR / GITKEEP, ""),
    ]

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
