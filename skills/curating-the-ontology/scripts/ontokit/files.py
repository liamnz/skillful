"""Code-link and staleness checks: E009, W105 and W107.

`implemented_in` paths are relative to the project root, which is the working
directory every command runs from (see SPEC "Commands").

W107 dates a proposal by git: a concept by the first commit that added its file, an
extension by the first commit that added its line to the manifest. Outside git, or
for a proposal that was never committed, W107 is skipped and a note says why.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from .context import Context
from .drift import git_path
from .findings import Finding, finding
from .gitinfo import Git
from .io import Ontology


def check_files(ontology: Ontology, ctx: Context) -> Iterator[Finding]:
    for concept in ontology.concepts.values():
        for impl in concept.implemented_in:
            path = Path(impl.path)
            if not path.is_file():
                yield finding(
                    "E009",
                    concept.id,
                    f"implemented_in path '{impl.path}' does not exist (relative to the project root, "
                    f"{Path.cwd().as_posix()}). Fix the path, or remove the entry if the code is gone.",
                )
                continue
            if impl.symbol and impl.symbol not in path.read_text(encoding="utf-8", errors="replace"):
                yield finding(
                    "W105",
                    concept.id,
                    f"Symbol '{impl.symbol}' is not in {impl.path}. Was it renamed? Update the symbol, "
                    "then check the definition still matches.",
                )


def _age_days(date: str, now: datetime) -> int:
    return (now - datetime.fromisoformat(date)).days


def check_stale_proposals(ontology: Ontology, ctx: Context) -> Iterator[Finding]:
    """W107: a concept or vocabulary extension still `proposed` after stale_proposal_days."""
    proposed_concepts = [c for c in ontology.concepts.values() if c.status == "proposed"]
    manifest = ontology.manifest
    proposed_extensions = []
    if manifest is not None:
        for section, extensions in (
            ("kinds", manifest.kind_extensions),
            ("relation_types", manifest.relation_extensions),
        ):
            proposed_extensions += [(section, i) for i, e in extensions.items() if e.get("status") == "proposed"]
    if not proposed_concepts and not proposed_extensions:
        return
    git: Git | None = ctx.git
    if git is None:
        ctx.note("Stale-proposal check (W107) skipped: not inside a git repository with at least one commit.")
        return

    limit = ontology.settings.stale_proposal_days
    now = datetime.now(UTC)
    uncommitted: list[str] = []
    for concept in proposed_concepts:
        date = git.first_commit_date(git_path(concept.source))
        if date is None:
            uncommitted.append(concept.id)
        elif (days := _age_days(date, now)) > limit:
            yield finding(
                "W107",
                concept.id,
                f"'{concept.id}' has been proposed for {days} days (stale_proposal_days is {limit}). Ask a human "
                "to define it, or remove it if it isn't needed.",
            )
    if manifest is not None:
        for section, ext_id in proposed_extensions:
            # POSIX regex (git -G): ids are snake_case, so they need no escaping.
            date = git.first_commit_date(git_path(manifest.source), f"^[[:space:]][[:space:]]*{ext_id}:")
            if date is None:
                uncommitted.append(f"extensions.{section}.{ext_id}")
            elif (days := _age_days(date, now)) > limit:
                yield finding(
                    "W107",
                    None,
                    f"extensions.{section}.{ext_id} has been proposed for {days} days (stale_proposal_days is "
                    f"{limit}). Ask a human to define it, or remove it if it isn't needed.",
                )
    if uncommitted:
        ctx.note(f"Stale-proposal check (W107) skipped for proposals not yet committed: {', '.join(uncommitted)}.")
