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


# Every finding code, with its severity and Gruber criterion (see SPEC "Validator checks").
# Criterion ids are stable: the view groups findings by them.
CODES: dict[str, tuple[Severity, str | None]] = {
    "E001": ("error", None),
    "E002": ("error", None),
    "E003": ("error", None),
    "E004": ("error", "coherence"),
    "E005": ("error", "coherence"),
    "E006": ("error", "coherence"),
    "E007": ("error", "coherence"),
    "E008": ("error", None),
    "E009": ("error", "drift"),
    "E010": ("error", "coherence"),
    "E011": ("error", "clarity"),
    "E012": ("error", "coherence"),
    "E013": ("error", "coherence"),
    "E014": ("error", "coherence"),
    "W101": ("warn", "clarity"),
    "W102": ("warn", "clarity"),
    "W103": ("warn", "minimal-encoding-bias"),
    "W104": ("warn", "coherence"),
    "W105": ("warn", "drift"),
    "W106": ("warn", "drift"),
    "W107": ("warn", "staleness"),
    "W108": ("warn", None),
    "W109": ("warn", "coherence"),
    "W110": ("warn", "coherence"),
    "W111": ("warn", "coherence"),
    "W112": ("warn", "coherence"),
    "W113": ("warn", "clarity"),
    "I201": ("info", "minimal-commitment"),
    "I202": ("info", "extendibility"),
    "I203": ("info", "minimal-commitment"),
    "I204": ("info", "clarity"),
    "I205": ("info", "drift"),
}


def finding(code: str, concept: str | None, message: str) -> Finding:
    """A Finding whose severity and criterion come from CODES."""
    severity, criterion = CODES[code]
    return Finding(code, severity, concept, criterion, message)


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
