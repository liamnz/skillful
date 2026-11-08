"""Validator checks: functions over a loaded Ontology that return Findings.

Structural findings (E001-E003) are produced while loading (see io.py). Every other
check is registered in CHECKS. Checks never print; git access goes through
`ctx.git` (gitinfo.py), and explanations that are not findings go to `ctx.note`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from . import drift, relations, staleness
from .context import Context
from .findings import Finding
from .io import Ontology

Check = Callable[[Ontology, Context], Iterable[Finding]]

CHECKS: list[Check] = [
    relations.check_relations,
    drift.check_drift,
    staleness.check_staleness,
]


def run_checks(ontology: Ontology, ctx: Context) -> list[Finding]:
    return [finding for check in CHECKS for finding in check(ontology, ctx)]
