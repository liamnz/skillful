"""The `validate` command: load, run every check, report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .checks import run_checks
from .findings import EXIT_ENVIRONMENT, EXIT_FINDINGS, EXIT_OK, Finding, sort_findings
from .io import OntologyNotFound, load


def collect(root: Path) -> list[Finding]:
    """All findings for the ontology at `root`, sorted. Raises OntologyNotFound."""
    ontology, findings = load(root)
    return sort_findings([*findings, *run_checks(ontology)])


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 or word == 'info' else 's'}"


def run(args: argparse.Namespace) -> int:
    try:
        findings = collect(Path(args.root))
    except OntologyNotFound as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return EXIT_ENVIRONMENT

    shown = findings[: args.limit] if args.limit is not None else findings
    if args.json:
        print(json.dumps([f.to_dict() for f in shown], indent=2, ensure_ascii=False))
    else:
        for f in shown:
            print(f"{f.severity:<5}  {f.code}  {f.concept or '-'}  {f.message}")

    counts = {sev: sum(f.severity == sev for f in findings) for sev in ("error", "warn", "info")}
    if not findings:
        sys.stderr.write("No findings.\n")
    else:
        sys.stderr.write(
            f"{_plural(counts['error'], 'error')}, {_plural(counts['warn'], 'warning')}, "
            f"{_plural(counts['info'], 'info')}.\n"
        )
    if len(shown) < len(findings):
        sys.stderr.write(f"Showing {len(shown)} of {len(findings)} findings (--limit {args.limit}).\n")

    if counts["error"] or (args.strict and counts["warn"]):
        return EXIT_FINDINGS
    return EXIT_OK
