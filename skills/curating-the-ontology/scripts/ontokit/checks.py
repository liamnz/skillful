"""Validator checks: pure functions over a loaded Ontology that return Findings.

Structural findings (E001-E003) are produced while loading (see io.py). Every other
check is registered in CHECKS and must never print or touch the filesystem directly.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from .findings import Finding
from .io import Ontology

Check = Callable[[Ontology], Iterable[Finding]]

CHECKS: list[Check] = []


def run_checks(ontology: Ontology) -> list[Finding]:
    return [finding for check in CHECKS for finding in check(ontology)]
