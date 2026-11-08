"""Per-run context handed to every check."""

from __future__ import annotations

from dataclasses import dataclass, field

from .gitinfo import Git


@dataclass
class Context:
    git: Git | None  # None outside a git repository (git-based checks are skipped)
    notes: list[str] = field(default_factory=list)  # diagnostics for stderr; not findings

    def note(self, message: str) -> None:
        if message not in self.notes:
            self.notes.append(message)
