"""Findings and exit codes shared by every command."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Literal

Severity = Literal["error", "warn", "info"]

# Documented exit codes (see SPEC "Script conventions").
EXIT_OK = 0
EXIT_FINDINGS = 1  # validation errors (or warnings with --strict) / stale build with --check
EXIT_USAGE = 2
EXIT_REFUSED = 3  # e.g. id already exists, core vocabulary id given
EXIT_ENVIRONMENT = 4  # e.g. not in a git repo when one is required

_SEVERITY_ORDER: dict[str, int] = {"error": 0, "warn": 1, "info": 2}


@dataclass(frozen=True)
class Finding:
    code: str  # e.g. "W103"
    severity: Severity
    concept: str | None
    criterion: str | None  # e.g. "coherence"; None for purely structural checks
    message: str

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


def sort_findings(findings: Iterable[Finding]) -> list[Finding]:
    """Deterministic order: severity, then concept id (global findings first), then code."""
    return sorted(
        findings,
        key=lambda f: (_SEVERITY_ORDER[f.severity], f.concept or "", f.code, f.message),
    )
