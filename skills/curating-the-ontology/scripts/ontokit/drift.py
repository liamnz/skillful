"""W106 (drift since last review) and I205 (unreachable reviewed_at).

W106 asks: has code relevant to this concept changed since a human last confirmed
the definition? For each `implemented_in` entry:

1. Baseline: `reviewed_at` if set and reachable from HEAD; otherwise the last commit
   that touched the concept file (and I205 if `reviewed_at` was set but unreachable).
2. Relevant change, between the baseline and the working tree:
   - with a symbol: an added or removed line within `drift_context_lines` of a line
     mentioning the symbol (plain substring match), in the old or new version;
   - without a symbol: any change to the file.
3. Proposed concepts are skipped: there is no confirmed definition to drift from.

It is a prompt to check, not a guarantee (see SPEC "Drift detection (W106)").
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from .context import Context
from .findings import Finding
from .gitinfo import Git, Hunk
from .io import Concept, Implementation, Ontology


def git_path(path: Path) -> str:
    """A path for git commands: relative to the working directory when possible."""
    try:
        return Path(os.path.relpath(path.resolve(), Path.cwd().resolve())).as_posix()
    except ValueError:  # different drive on Windows
        return path.resolve().as_posix()


def _mentions(text: str, symbol: str) -> list[int]:
    return [n for n, line in enumerate(text.splitlines(), start=1) if symbol in line]


def _near(lines: tuple[int, ...], mentions: list[int], distance: int) -> bool:
    return any(abs(line - m) <= distance for line in lines for m in mentions)


def changed_near_symbol(git: Git, base: str, impl: Implementation, distance: int) -> bool:
    hunks: list[Hunk] = git.diff_hunks(base, impl.path)
    if not hunks:
        return False
    if impl.symbol is None:
        return True
    old_mentions = _mentions(git.show(base, impl.path), impl.symbol)
    path = Path(impl.path)
    new_text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    new_mentions = _mentions(new_text, impl.symbol)
    return any(_near(h.removed, old_mentions, distance) or _near(h.added, new_mentions, distance) for h in hunks)


def _baseline(git: Git, concept: Concept, impl: Implementation) -> tuple[str | None, Finding | None]:
    """The commit to compare against, and an I205 finding if reviewed_at is unreachable."""
    if impl.reviewed_at is not None:
        if git.is_reachable(impl.reviewed_at):
            return impl.reviewed_at, None
        i205 = Finding(
            "I205",
            "info",
            concept.id,
            "drift",
            f"{impl.path}: reviewed_at {impl.reviewed_at} is not in the history of HEAD (after a rebase or "
            "squash?). Drift is measured from the concept file's last commit instead. "
            f"Once the definition is confirmed, run 'onto.py review {concept.id}' to record a new review.",
        )
        return git.last_commit(git_path(concept.source)), i205
    return git.last_commit(git_path(concept.source)), None


def check_drift(ontology: Ontology, ctx: Context) -> Iterator[Finding]:
    git = ctx.git
    if git is None:
        if any(c.implemented_in for c in ontology.concepts.values()):
            ctx.note("Drift and staleness checks skipped: not inside a git repository with at least one commit.")
        return
    distance = ontology.settings.drift_context_lines
    for concept in ontology.concepts.values():
        if concept.status == "proposed" or not concept.implemented_in:
            continue
        for impl in concept.implemented_in:
            base, i205 = _baseline(git, concept, impl)
            if i205 is not None:
                yield i205
            if base is None:
                ctx.note(
                    f"Drift check skipped for '{concept.id}': its concept file has never been committed, "
                    "so there is no baseline yet."
                )
                continue
            if changed_near_symbol(git, base, impl, distance):
                since = "its last review" if impl.reviewed_at and i205 is None else "the concept was last edited"
                where = f" near '{impl.symbol}'" if impl.symbol else ""
                yield Finding(
                    "W106",
                    "warn",
                    concept.id,
                    "drift",
                    f"{impl.path}: code{where} changed since {since} ({git.short(base)}). Check that the "
                    f"definition still matches, then record it with 'onto.py review {concept.id}'.",
                )
