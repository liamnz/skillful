# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

This repo develops [Agent Skills](https://agentskills.io/specification) for data teams. Each directory under `skills/` is a product: that one directory gets copied into a toolkit repo and then into target projects. Everything else (`tests/`, `examples/`, `docs/`, `tasks/`) is dev-only and never ships, and has one folder per skill.

| Skill | Purpose | Spec | Tests | Examples | Tasks |
|---|---|---|---|---|---|
| `curating-the-ontology` | Keep a human-owned domain ontology in a project's `docs/ontology/` | `docs/ontology-skill/SPEC.md` | `tests/ontology/` | `examples/ontology/` | `tasks/ontology/` |
| `designing-the-architecture` (in development) | Record a target architecture that changes only through accepted decisions | `docs/architecture-skill/SPEC.md` | `tests/architecture/` | `examples/architecture/` | `tasks/architecture/` |

Each spec is approved and authoritative, and includes an Always / Ask first / Never list under "Boundaries". Read the relevant section before changing behaviour. The files in `tasks/<skill>/` are historical records of the implementation, so old paths in them are expected.

## Shared conventions

### Commands

There is deliberately no `pyproject.toml`, so `uv run` never treats this repo as a project. Dev tools are supplied with `--with`, and config lives in `pytest.ini` and `ruff.toml`. Do not add a `pyproject.toml`.

```bash
# All non-browser tests, for every skill (browser test modules skip themselves when playwright is absent)
uv run --with pytest --with pyyaml --with jsonschema pytest tests/ -q

# One skill's tests
uv run --with pytest --with pyyaml --with jsonschema pytest tests/ontology -q

# Full suite including browser tests; needed for any change to a skill's generated page
uv run --with pytest --with pytest-playwright --with pyyaml --with jsonschema pytest tests/ -q

# Lint and format check
uv run --with ruff ruff check .
uv run --with ruff ruff format --check .
```

If browser tests error with "Executable doesn't exist", `uv` has resolved a newer Playwright than the Chromium installed on this machine. Either add `--with playwright==<version>` to match the installed browser, or install the browser for the new version.

### Rules that hold for every skill

- **A skill directory is self-contained and harness-neutral.** Nothing in it may reference `tests/`, `examples/`, `tasks/`, `SPEC.md` or `../`, and it must avoid harness terms such as hooks, slash commands, subagents, tool names and product names like Cursor or Claude Code. Scripts find `assets/` through `__file__`. One skill never imports from another.
- **Each skill's tests stand alone.** There is no shared `tests/conftest.py`. Module prefixes (`test_onto_`, `test_arch_`) keep names unique, and each suite's helpers live in a uniquely named module (`ontotest.py`, `archtest.py`), so `conftest.py` holds only pytest fixtures.
- **Authorship is the core product rule.** Agents never take a decision that the skill reserves for a human. This applies to any skill behaviour you change, and to the records under `examples/`.
- **Ask first** before adding a runtime dependency, changing a schema or core vocabulary, or upgrading D3. CI and pre-commit wiring are out of scope.

### Git workflow

Work on a branch per phase or track off `main`, with one conventional commit per task (e.g. `docs(evals): T27 ...`). Merge into `main` with `--no-ff` only after the checkpoint passes and the user approves. Don't push unless asked.

## Skill: `curating-the-ontology`

Lives in `skills/curating-the-ontology/`. Its spec is `docs/ontology-skill/SPEC.md`, and `tasks/ontology/` records the implementation history (tasks T1–T27).

### Commands

```bash
# A single file or test
uv run --with pytest --with pyyaml --with jsonschema pytest tests/ontology/test_onto_validate.py -q
uv run --with pytest --with pyyaml --with jsonschema pytest tests/ontology/test_onto_finding_coverage.py -q -k E004

# Run the CLI (from the root of a project that has docs/ontology/, e.g. examples/ontology/sample-project)
uv run --script <path-to>/skills/curating-the-ontology/scripts/onto.py validate

# Regenerate golden JSON after an intended output change (PowerShell: set $env:UPDATE_GOLDEN=1 first)
UPDATE_GOLDEN=1 uv run --with pytest --with pyyaml --with jsonschema pytest tests/ontology/test_onto_conventions.py -q

# Generate the git-ignored 300-concept fixture for manual review
python tests/ontology/gen_large_fixture.py
```

`tests/ontology/test_onto_packaging.py` runs the Agent Skills validator offline and skips if it isn't cached. Fetch it once with `uvx --from skills-ref==0.1.1 agentskills --help`.

### Architecture

**CLI.** `scripts/onto.py` is a PEP 723 entry point over the `ontokit` package, always run as `uv run --script` so it never touches the host project's Python environment. `cli.py` only parses and dispatches to each command module's `run(args)`. Runtime dependencies are limited to `pyyaml` and `jsonschema`. Commands never prompt. Results go to stdout and diagnostics to stderr, every write command honours `--dry-run`, and exit codes 0–4 are a documented contract.

**Validation pipeline.** `validate.collect` produces all findings. Structural findings (E001–E003) come from loading in `io.py`; everything else comes from the check functions registered in `checks.CHECKS`, which take `(Ontology, Context)` and return `Finding`s without printing. Git access goes only through `ctx.git` (`gitinfo.py`), and `Context(git=None)` is how checks run without git. Findings are sorted deterministically.

**Finding codes are defined in several places that tests keep in sync.** A new or changed code needs all of:
- the `CODES` registry in `findings.py`;
- the table in `docs/ontology-skill/SPEC.md` (`test_onto_finding_coverage.py` parses it);
- a fixture in `tests/ontology/fixtures/cases/<code>/`, or an entry in `SCENARIOS` for git- and build-based codes;
- a mention under the right heading in `references/gruber-criteria.md` (`test_onto_packaging.py`).

Changing finding codes is an "ask first" item in the spec.

**HTML explorer.** `build.py` assembles one self-contained `index.html` by filling `{{PLACEHOLDER}}`s in `assets/html/index.html` with the CSS, the vendored D3 modules (in `vendor/MANIFEST.json` order), the app scripts (`APP_SCRIPTS` order) and the records as embedded JSON. Output must be byte-for-byte reproducible, with no timestamps, and is covered by a CSP of `default-src 'none'`. `graph-model.js` holds pure graph logic with no D3; `graph-view.js` does layout and rendering, with D3 used only for physics and gestures. The layout is seeded and runs a fixed number of ticks, so positions are deterministic.

**Tests.** `conftest.py` holds pytest fixtures, and helpers are imported from `ontotest.py`. `make_project` overlays `tests/ontology/fixtures/cases/<case>/` onto a copy of `tests/ontology/fixtures/baseline/`, so a case contains only the files it adds or replaces. The baseline must stay free of findings. `run_onto` runs the real CLI through `uv` with stdin closed, while `collect_findings` is the fast in-process route for check tests. `examples/ontology/sample-project` is also a test input: its findings must match `expected-findings.yaml`, and the eval scenarios depend on deliberate flaws in it (such as the 90-day definition against the 30-day code in `active-customer`), so don't "fix" those.

### Rules that tests enforce or the design depends on

- **Harness terms** are listed in `DENYLIST` in `test_onto_packaging.py`.
- **`SKILL.md` limits.** The body stays under 500 lines and about 3,800 words, "Hard rules" is the first section, and every file in `references/` is linked with a "read when" trigger. References don't link onward.
- **Version** lives in `SKILL.md` under `metadata.version`, and `--version` reads it from there.
- **Explorer styling.** Raw colour, size and spacing values belong only in `assets/html/tokens.css`, and contrast and colour-blind safety are tested. Chrome stays neutral grey, with colour reserved for kind, severity and focus. No shadows, gradients or decoration. Desktop only, minimum 1280×720.
- **Vendored D3** is pinned and checksummed in `vendor/MANIFEST.json`; every file there must be listed.
- **Authorship.** Agents never write or alter a `definition`, set `status: defined`, or run `review` on their own authority.
- **Ask first** also covers changing the concept schema or `schema_version`.

## Skill: `designing-the-architecture`

In development. Not yet present under `skills/`. See `docs/architecture-skill/SPEC.md` and `tasks/architecture/plan.md`. Its tests will live in `tests/architecture/`, with helpers in `archtest.py`. This section is completed by task A33.
