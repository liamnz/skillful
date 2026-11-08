# Baseline fixture

A small, valid ontology that must produce **zero errors and zero warnings** from every
check. Each finding code has a case in `tests/fixtures/cases/<code>/` that is overlaid
on a copy of this baseline (files added or replaced) to trigger exactly that code.

When adding a check, keep this baseline clean: fix the baseline, not the check.
