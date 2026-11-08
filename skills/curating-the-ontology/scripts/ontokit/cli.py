"""Command-line interface: argument parsing and dispatch only.

Every command is non-interactive. Results go to stdout; diagnostics to stderr.
Commands are implemented in their own modules and registered in `HANDLERS`.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from typing import NoReturn

from . import skill_version
from .findings import EXIT_USAGE

PROG = "onto.py"
DEFAULT_ROOT = "docs/ontology"
RUN = "uv run --script $SKILL/scripts/onto.py"

Handler = Callable[[argparse.Namespace], int]


class Parser(argparse.ArgumentParser):
    """ArgumentParser whose errors are actionable and exit with the usage code."""

    def error(self, message: str) -> NoReturn:
        sys.stderr.write(f"Error: {message}\nRun '{self.prog} --help' for usage and examples.\n")
        sys.exit(EXIT_USAGE)


def _examples(*lines: str) -> str:
    return "Examples:\n" + "\n".join(f"  {RUN} {line}" for line in lines)


def _command(subparsers: argparse._SubParsersAction, name: str, summary: str, examples: str, parents: list) -> Parser:
    return subparsers.add_parser(
        name,
        help=summary,
        description=summary,
        epilog=examples,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=parents,
    )


def _not_implemented(args: argparse.Namespace) -> int:
    sys.stderr.write(f"Error: '{args.command_path}' is not implemented yet.\n")
    return EXIT_USAGE


def build_parser() -> Parser:
    # Accept --root after the subcommand too; SUPPRESS keeps the top-level default.
    root_opt = Parser(add_help=False)
    root_opt.add_argument("--root", default=argparse.SUPPRESS, help=f"ontology directory (default: {DEFAULT_ROOT})")
    dry_run = Parser(add_help=False)
    dry_run.add_argument("--dry-run", action="store_true", help="print what would change; write nothing")
    common = [root_opt]

    parser = Parser(
        prog=PROG,
        description="Curate a human-owned domain ontology in docs/ontology/.",
        epilog=_examples("validate --json", 'new churned-account --name "Churned account" --kind entity'),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"{PROG} {skill_version()}")
    parser.add_argument("--root", default=DEFAULT_ROOT, help=f"ontology directory (default: {DEFAULT_ROOT})")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p = _command(
        sub,
        "init",
        "Scaffold docs/ontology/ with a manifest and an empty concepts/ folder.",
        _examples('init --name "Acme Analytics" --agents-md --gitattributes', "init --no-agents-md --dry-run"),
        [*common, dry_run],
    )
    p.add_argument("--name", help="human-readable ontology name for the manifest")
    agents = p.add_mutually_exclusive_group()
    agents.add_argument(
        "--agents-md",
        dest="agents_md",
        action="store_true",
        default=None,
        help="add the always-on pointer section to AGENTS.md (ask the user first)",
    )
    agents.add_argument("--no-agents-md", dest="agents_md", action="store_false", help="leave AGENTS.md untouched")
    attrs = p.add_mutually_exclusive_group()
    attrs.add_argument(
        "--gitattributes",
        dest="gitattributes",
        action="store_true",
        default=None,
        help="mark index.html as generated in .gitattributes (ask the user first)",
    )
    attrs.add_argument(
        "--no-gitattributes", dest="gitattributes", action="store_false", help="leave .gitattributes untouched"
    )

    p = _command(
        sub,
        "new",
        "Create a status=proposed concept stub. Definitions are written by humans.",
        _examples(
            'new churned-account --name "Churned account" --kind entity \\\n'
            '      --rationale "Introduced in models/marts/fct_churn.sql" \\\n'
            "      --implemented-in models/marts/fct_churn.sql:is_churned",
        ),
        [*common, dry_run],
    )
    p.add_argument("id", help="kebab-case concept id; becomes concepts/<id>.yaml")
    p.add_argument("--name", required=True, help="the one canonical term for the concept")
    p.add_argument("--kind", required=True, help="a core kind or a declared kind extension")
    p.add_argument("--rationale", help="why the agent is proposing this concept")
    p.add_argument("--suggested-definition", help="optional agent suggestion, shown labelled as such")
    p.add_argument(
        "--implemented-in",
        action="append",
        default=[],
        metavar="PATH[:SYMBOL]",
        help="repo-relative file (and optional symbol) implementing the concept; repeatable",
    )

    vocab = _command(
        sub,
        "vocab",
        "Propose or list vocabulary: kinds and relation types.",
        _examples("vocab list", 'vocab new kind rule --rationale "..."'),
        common,
    )
    vocab_sub = vocab.add_subparsers(dest="vocab_command", metavar="<subcommand>")
    vnew = _command(
        vocab_sub,
        "new",
        "Propose a vocabulary extension (status=proposed).",
        _examples(
            'vocab new kind rule --rationale "Policies recur across models; no core kind fits."',
            'vocab new relation measures --inverse measured_by --from metric --to entity event --rationale "..."',
        ),
        common,
    )
    vnew_sub = vnew.add_subparsers(dest="vocab_new_type", metavar="<kind|relation>")
    p = _command(
        vnew_sub,
        "kind",
        "Propose a kind extension.",
        _examples('vocab new kind rule --rationale "Policies recur across models; no core kind fits."'),
        [*common, dry_run],
    )
    p.add_argument("id", help="snake_case extension id")
    p.add_argument("--rationale", required=True, help="why no existing kind fits")
    p = _command(
        vnew_sub,
        "relation",
        "Propose a relation-type extension.",
        _examples(
            'vocab new relation measures --inverse measured_by --from metric --to entity event --rationale "..."'
        ),
        [*common, dry_run],
    )
    p.add_argument("id", help="snake_case extension id")
    p.add_argument("--inverse", required=True, help="label for the relation read from target to source")
    p.add_argument("--acyclic", action="store_true", help="forbid cycles through this relation type")
    p.add_argument("--from", dest="from_kinds", nargs="+", default=[], metavar="KIND", help="allowed source kinds")
    p.add_argument("--to", dest="to_kinds", nargs="+", default=[], metavar="KIND", help="allowed target kinds")
    p.add_argument("--rationale", required=True, help="why no existing relation type fits")
    p = _command(
        vocab_sub,
        "list",
        "List core and extension vocabulary with status and usage counts.",
        _examples("vocab list", "vocab list --json"),
        common,
    )
    p.add_argument("--json", action="store_true", help="machine-readable output on stdout")

    p = _command(
        sub,
        "review",
        "Record that a human confirmed the definition still matches the code (sets reviewed_at to HEAD).",
        _examples("review active-customer", "review active-customer --path models/marts/dim_customer.sql"),
        [*common, dry_run],
    )
    p.add_argument("id", help="concept id")
    p.add_argument("--path", help="only review this implemented_in path")

    p = _command(
        sub,
        "validate",
        "Health check: schema, coherence, clarity, drift and staleness findings.",
        _examples("validate", "validate --json --limit 50", "validate --strict"),
        common,
    )
    p.add_argument("--json", action="store_true", help="machine-readable findings on stdout")
    p.add_argument("--strict", action="store_true", help="exit 1 on warnings as well as errors")
    p.add_argument("--limit", type=int, metavar="N", help="show at most N findings")

    p = _command(
        sub,
        "impact",
        "List concepts touched by changed files, and changed files mapped to no concept.",
        _examples("impact", "impact --base main --json"),
        common,
    )
    p.add_argument(
        "--base", metavar="GIT-REF", help="compare against this ref (default: merge-base with the default branch)"
    )
    p.add_argument("--json", action="store_true", help="machine-readable output on stdout")
    p.add_argument("--limit", type=int, metavar="N", help="show at most N entries per list")

    p = _command(
        sub,
        "build",
        "Write the self-contained docs/ontology/index.html view.",
        _examples("build", "build --check"),
        [*common, dry_run],
    )
    p.add_argument("--check", action="store_true", help="write nothing; exit 1 if index.html is stale")

    return parser


def _handlers() -> dict[str, Handler]:
    """Command path (e.g. "vocab new kind") -> handler, imported lazily to keep --help fast."""
    from . import build, init, new, review, validate

    return {
        "init": init.run,
        "new": new.run,
        "review": review.run,
        "validate": validate.run,
        "build": build.run,
    }


def _command_path(args: argparse.Namespace) -> str:
    parts = [args.command, getattr(args, "vocab_command", None), getattr(args, "vocab_new_type", None)]
    return " ".join(p for p in parts if p)


def _help_for(parser: Parser, path: str) -> Parser:
    """Find the (sub)parser for a partial command path such as 'vocab new'."""
    current: argparse.ArgumentParser = parser
    for word in path.split():
        actions = [a for a in current._actions if isinstance(a, argparse._SubParsersAction)]
        current = actions[0].choices[word]
    return current  # type: ignore[return-value]


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(argv)
    path = _command_path(args)
    args.command_path = path

    leaf_commands = {
        "init",
        "new",
        "vocab new kind",
        "vocab new relation",
        "vocab list",
        "review",
        "validate",
        "impact",
        "build",
    }
    if path not in leaf_commands:
        # No command, or an incomplete one such as `vocab` or `vocab new`.
        _help_for(parser, path).print_help(sys.stderr)
        return EXIT_USAGE

    return _handlers().get(path, _not_implemented)(args)
