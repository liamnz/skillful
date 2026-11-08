# Tasks: `curating-the-ontology` skill

*Plan: [tasks/plan.md](plan.md). Spec: [docs/SPEC.md](../docs/SPEC.md). `SK` = `skills/curating-the-ontology`.*

**Standard verification commands**

```bash
uv run --with pytest --with pyyaml --with jsonschema pytest tests/ -q                     # PYTEST
uv run --with ruff ruff check . && uv run --with ruff ruff format --check .               # LINT
uv run --with pytest --with pytest-playwright --with pyyaml --with jsonschema pytest tests/test_html_ui.py -q   # UI (from T9)
```

**Definition of done:**
- Every task: PYTEST and LINT are green. New behaviour has tests. Fixtures count as data, not toward the file limit.
- Every task that touches the view: UI is also green.
- `SK/` never references anything outside itself.

---

## Phase 1: Foundation

### T1: Walking skeleton
**Description:** Create the self-contained skill directory and a CLI shell that runs via `uv run --script` from any location. Also add `Finding`, exit-code constants and the dev tooling config, so every later task has a place to land.

**Acceptance criteria:**
- [x] `uv run --script SK/scripts/onto.py --help` and `--version` work from the repo root and from a copy of `SK/` in a nested temp directory (Decision 1).
- [x] An unknown subcommand or bad flag exits `2` with an actionable message on stderr. Every subcommand from the spec is registered with its `--help` text and examples, and an unimplemented one exits `2` with "not implemented yet".
- [x] `SKILL.md` has spec-conformant frontmatter (name, description, compatibility, metadata.version) and a placeholder body. `--version` reads the same version.

**Verification:** PYTEST (`tests/test_cli.py`), LINT. Manually: `--help` output reads well.

**Dependencies:** None

**Files:** `SK/SKILL.md`, `SK/scripts/onto.py`, `SK/scripts/ontokit/{__init__,cli,findings}.py`, `ruff.toml` + `pytest.ini` (dev config; used instead of a `pyproject.toml` so `uv run` never treats this repo as a project), `.gitattributes` (LF normalisation), `.gitignore`, `tests/test_cli.py`

**Scope:** M

### T2: Schemas, core vocabulary, loader and `validate` (E001–E003)
**Description:** Define the record contracts and load an ontology into an immutable model. Ship `validate` with the first three checks, `--json` output, sorted findings and exit codes 0, 1 and 2.

**Acceptance criteria:**
- [x] `concept.schema.json` and `manifest.schema.json` (2020-12) cover every spec field, including the `cardinality` enum, `implemented_in.reviewed_at`, `proposal` and `replaced_by`. `core-vocabulary.yaml` holds the four kinds and four relations, with definitions, inverses, acyclicity, `from`/`to` and fixed encodings.
- [x] The valid baseline fixture produces zero findings and exit `0`. The E001, E002 and E003 fixtures each produce exactly that code and exit `1`.
- [x] `validate --json` prints findings to stdout sorted by (severity, concept, code). The human-readable report also goes to stdout (it is the command's result); the summary line and diagnostics go to stderr.

**Verification:** PYTEST (`tests/test_validate.py`), LINT

**Dependencies:** T1

**Files:** `SK/assets/schemas/{concept.schema.json,manifest.schema.json,core-vocabulary.yaml}`, `SK/scripts/ontokit/{io,schema,checks}.py`, `tests/test_validate.py`, `tests/conftest.py`, `tests/fixtures/baseline/`, `tests/fixtures/cases/{e001,e002,e003}/` (cases are overlays copied onto the baseline)

**Scope:** M

### T3: `init`
**Description:** Scaffold `docs/ontology/` with a manifest that has no active extensions and the commented-out starter extensions (`rule`, `has`, `derived_from`, `measures`).

**Acceptance criteria:**
- [x] `init [--name]` in an empty git repo creates `ontology.yaml` and `concepts/`, and `validate` then exits `0` with no warnings.
- [x] Re-running is idempotent: existing files are left byte-identical, and stderr reports what already exists. `--dry-run` writes nothing and lists the planned writes.
- [x] Without `--agents-md`/`--no-agents-md`, it prints a one-line hint about the `AGENTS.md` pointer to stderr. The flags themselves are implemented in T23.

**Verification:** PYTEST (`tests/test_init.py`), LINT

**Dependencies:** T2

**Files:** `SK/assets/templates/ontology.yaml`, `SK/scripts/ontokit/init.py`, `SK/scripts/ontokit/cli.py`, `tests/test_init.py`

**Scope:** S

### T4: `new`
**Description:** Create `status: proposed` concept stubs with an optional rationale, suggested definition and `implemented_in` entries.

**Acceptance criteria:**
- [x] `new <id> --name --kind [--rationale] [--suggested-definition] [--implemented-in path[:symbol]]...` writes a schema-valid `proposed` record whose filename equals its id. The path/symbol split is on the *last* colon, and paths are stored repo-relative in POSIX form.
- [x] An existing id is refused with exit `3`. There is no way to set any other status. An invalid id or kind exits `2` with the actionable message format from the spec, listing the valid kinds.
- [x] `--dry-run` prints the record and writes nothing.

**Verification:** PYTEST (`tests/test_new.py`), LINT

**Dependencies:** T2 (T3 for the round-trip test)

**Files:** `SK/scripts/ontokit/new.py`, `SK/scripts/ontokit/cli.py`, `tests/test_new.py`

**Scope:** S

### Checkpoint 1: Foundation
- [x] `init → new → validate` round trip in a temp git repo (`tests/test_roundtrip.py`).
- [x] PYTEST and LINT green. Copying `SK/` elsewhere still works.
- [x] Quick review with you of the CLI ergonomics (`--help` text, error messages).

---

## Phase 2: Risk first

### T5: Git layer, W106 drift, `review`, I205
**Description:** Build the only module that talks to git. Implement W106 exactly as specified and the `review` command, which records `reviewed_at` with a comment-preserving text edit (Decision 2).

**Acceptance criteria:**
- [x] All six W106 cases from the spec pass in temp repos:
  - an unrelated edit elsewhere in a shared file does not fire;
  - an edit near the symbol fires;
  - with no symbol, any change to the file fires;
  - `review` clears it;
  - an unrelated edit to the concept file doesn't clear it once `reviewed_at` exists;
  - an unreachable `reviewed_at` falls back to the concept file's last commit and reports I205.
- [x] Uncommitted changes count. `proposed` concepts are skipped. Outside git, or for uncommitted concept files, the check is skipped with an info notice and no crash. Paths work on Windows.
- [x] `review <id> [--path]` sets `reviewed_at` to HEAD only on the targeted entries, leaving every other byte of the file unchanged. It refuses an unknown id or path (exit `3`), exits `4` outside a git repo, and supports `--dry-run`.

**Verification:** PYTEST (`tests/test_drift.py`, `tests/test_review.py`), LINT

**Dependencies:** T2

**Files:** `SK/scripts/ontokit/{gitinfo,context,drift,review}.py`, `SK/scripts/ontokit/{checks,validate,cli}.py`, `tests/test_drift.py`, `tests/test_review.py`, `tests/conftest.py`

**Scope:** M (highest-risk task; do it first in this phase)

### T6: Sample project
**Description:** A small dbt-style repo with a populated ontology. It is used by the mockup, by manual review and by the Cursor evals.

**Acceptance criteria:**
- [x] About 15–25 concepts covering all four core kinds, plus:
  - two defined extensions (e.g. `has`, `measures`) and one proposed extension;
  - at least one each of: a cardinality, a discouraged term, a `proposed` concept with a suggestion, `related_to`, an open question;
  - SQL models referenced by `implemented_in`.
- [x] Definitions are written as a human would write them. They are clearly sample content, but realistic enough to exercise the critique scenarios: one definition deliberately contradicts its SQL, for eval (d).
- [x] `validate` runs on it. Its findings are the deliberate ones only, listed in the project's README and in `expected-findings.yaml` (the test fails on anything else).

**Verification:** PYTEST (a smoke test that validates the sample and compares its findings to the expected list). Manually: you skim the definitions.

**Dependencies:** T2 (domain: generic "Acme" e-commerce/subscriptions)

**Files:** `examples/sample-project/{README.md, models/*.sql, docs/ontology/**}`, `tests/test_sample_project.py`

**Scope:** M (mostly data)

### T7: Design tokens and static mockup (human gate)
**Description:** Turn the Visual design section into `tokens.css` and a static, hand-laid-out mockup that uses sample-project data.

**Acceptance criteria:**
- [x] `tokens.css` defines every token in the spec (neutrals, `--kind-1..8`, semantic colours, typography, spacing, radii, motion), with light and dark values and reduced-motion handling.
- [x] `examples/design/mockup.html` shows the following, in both themes (with a theme toggle) at 1280×720:
  - the graph with one concept selected and its neighbourhood highlighted;
  - the detail pane, including a cardinality sentence and an agent-suggestion block;
  - the legend;
  - a finding badge.
- [x] **You explicitly approve the mockup.** Feedback is folded into `tokens.css` and the spec's Visual design section, and that spec change is committed.

**Verification:** Manually: review with you in the browser. Automated: the mockup uses no raw colour values outside `tokens.css` (grep).

**Dependencies:** T6

**Files:** `SK/assets/html/tokens.css`, `examples/design/mockup.html`, `docs/SPEC.md` (only if feedback changes it)

**Scope:** S–M

### T8: Vendor D3 and the build pipeline
**Description:** Pin and vendor the D3 modules, and implement `build` to produce a self-contained, byte-reproducible `index.html`. The page embeds the data contract (Decision 4) and a line-ending-insensitive `inputHash` (Decision 5). Adds `build --check` and W108. **Asks you before downloading.**

**Acceptance criteria:**
- [x] `assets/vendor/` holds the official UMD builds of `d3-selection`, `d3-force`, `d3-zoom`, `d3-drag`, `d3-shape` and their dependencies, at exact versions. `MANIFEST.json` gives the module, version, source URL, SHA-256 and order, and `LICENSE-d3.txt` holds the licence. The ISC notice is emitted in the output.
- [x] `build` writes one `index.html` with all CSS, JS and data inline and no `http(s)://` in `src`/`href`/`@import`. Two builds in different directories and at different times are byte-identical. A CRLF copy of the inputs produces the same `inputHash`.
- [x] `build --check` exits `1` when the output is stale, and `validate` reports W108. `--dry-run` writes nothing. The placeholder page shows concept and relation counts from the embedded data.

**Verification:** PYTEST (`tests/test_build.py`: static checks, reproducibility, vendor integrity, W108). Manually: open the sample build from `file://`.

**Dependencies:** T2 (T6 for the manual check)

**Files:** `SK/assets/vendor/*` (data), `SK/scripts/ontokit/build.py`, `SK/assets/html/{index.html,app.js}`, `SK/scripts/ontokit/cli.py`, `tests/test_build.py`

**Scope:** M

### T9: Deterministic graph render
**Description:** The spine of the view: a seeded, fixed-tick force layout rendered once as SVG, with each concept as a box enclosing its name, the kind (glyph colour + shape), status (box outline) and relation type (edge labels; hollow arrowhead for `is_a`, dashed undirected `related_to`) encodings, plus edge labels with halos. Styled only via tokens, per the approved mockup. Sets up the Playwright harness. **Asks you before downloading Chromium.**

**Acceptance criteria:**
- [x] One box per concept and one edge per relation (`related_to` without an arrowhead), with no two boxes overlapping. Core kinds use their fixed slots and glyph shapes.
- [x] Two loads of the same build give identical node positions. There is no animated settling.
- [x] Loads from `file://` with the network blocked and zero console errors. The sample project visually matches the approved mockup's structure and style.

**Verification:** UI (`tests/test_html_ui.py` and `tests/conftest.py` with a build fixture and network blocking), PYTEST, LINT. Manually: compare with the mockup.

**Dependencies:** T7 (approved), T8

**Files:** `SK/assets/html/{graph-model.js,graph-view.js,app.css,app.js}`, `tests/test_html_ui.py`, `tests/conftest.py`

**Scope:** M

### Checkpoint 2: De-risked
- [x] W106 temp-repo tests green. `review` preserves file bytes.
- [x] The sample project's graph renders deterministically from `file://`.
- [x] **You look at the first real graph.** Any design drift from the mockup is fixed in tokens, not ad hoc.

---

## Phase 3: Validator completion (Python track)

### T10: Relation checks
**Description:** The graph-integrity checks over relations, including the cardinality rules.

**Acceptance criteria:**
- [x] E004, E006 (cycles in any `acyclic` type, core or extension, with the cycle path in the message), E013, E014, W104, W111 and I204 each have a triggering fixture and produce exactly their code.
- [x] E013 covers cardinality on `is_a`/`attribute_of` and `1:N`/`N:1` on `related_to`. E014 covers the same relationship stated twice with conflicting cardinality.
- [x] The baseline stays clean.

**Verification:** PYTEST (`tests/test_checks_relations.py`), LINT

**Dependencies:** T2

**Files:** `SK/scripts/ontokit/checks.py` (or `checks/relations.py`), `tests/test_checks_relations.py`, fixtures

**Scope:** S–M

### T11: Term and definition checks
**Description:** Checks for the one-term-per-concept rule and definition quality.

**Acceptance criteria:**
- [x] E007, E008, W101 (uses `min_definition_words`), W102, W103, W109, I201 and I202 each have a triggering fixture and produce exactly their code.
- [x] Term matching is case-insensitive and whole-word, so "customer" doesn't match "customers_raw". This is documented in the check docstrings and tested with near-miss fixtures.
- [x] The baseline stays clean.

**Verification:** PYTEST (`tests/test_checks_terms.py`), LINT

**Dependencies:** T2

**Files:** `SK/scripts/ontokit/checks.py` (or `checks/terms.py`), `tests/test_checks_terms.py`, fixtures

**Scope:** S–M

### T12: Vocabulary extensions: checks and commands
**Description:** Govern extensions like concepts. Covers `vocab new kind|relation` (comment-preserving insertion into `ontology.yaml`) and `vocab list` with usage counts.

**Acceptance criteria:**
- [x] E005, E010, E011, E012, W110, W112, W113 and I203 each have a triggering fixture.
- [x] `vocab new` adds only `proposed` extensions with a rationale. It refuses core ids and duplicates (exit `3`), leaves the rest of `ontology.yaml` byte-identical, and supports `--dry-run`. `vocab list [--json]` shows core and extensions, with status, `from`/`to` and usage counts.
- [x] Success criterion 2a: uncommenting all the starter extensions in a fresh `init` manifest validates cleanly.

**Verification:** PYTEST (`tests/test_vocab.py`), LINT

**Dependencies:** T2, T3

**Files:** `SK/scripts/ontokit/{vocab,checks}.py`, `SK/scripts/ontokit/cli.py`, `tests/test_vocab.py`, fixtures

**Scope:** M

### T13: Filesystem, staleness and `impact`
**Description:** The remaining code-linked checks, and the `impact` command that drives end-of-task proposals.

**Acceptance criteria:**
- [x] E009, W105 and W107 (using the git date and `stale_proposal_days`, for concepts and extensions alike) are tested, including the graceful skip outside git.
- [x] `impact [--base] [--json] [--limit]` lists changed files (committed since the merge-base with the default branch, plus uncommitted and untracked files), the concepts referencing each file, and unmapped changed files. When the default branch can't be determined, it exits `4` with advice to pass `--base`.
- [x] Deterministic ordering, with golden JSON for one temp-repo scenario.

**Verification:** PYTEST (`tests/test_impact.py`, `tests/test_checks_files.py`), LINT

**Dependencies:** T5

**Files:** `SK/scripts/ontokit/{impact,checks}.py`, `SK/scripts/ontokit/cli.py`, `tests/test_impact.py`, `tests/test_checks_files.py`

**Scope:** M

### T14: CLI conventions hardening
**Description:** Make the script conventions hold across all commands, and lock the output formats.

**Acceptance criteria:**
- [x] `validate --strict` exits `1` on warnings. `--limit` caps findings and impact lists, reporting the truncation on stderr. A `schema_version` mismatch gives an actionable message.
- [x] Golden `--json` files exist for `validate` (baseline + multi-finding fixture), `vocab list` and `impact`. Each exit code 0–4 has at least one test.
- [x] A sweep test confirms every command supports `--help`, runs with stdin closed without hanging (with a timeout), and that every write command writes nothing under `--dry-run`.

**Verification:** PYTEST (`tests/test_conventions.py`), LINT

**Dependencies:** T10–T13

**Files:** `SK/scripts/ontokit/cli.py`, `tests/test_conventions.py`, `tests/golden/*`

**Scope:** S–M

### Checkpoint 3: Validator complete
- [x] Every finding code in the spec table has a fixture that triggers it. The baseline triggers none (a parametrised test that reads the code list from the checks registry).
- [x] Success criteria 1–5a pass. PYTEST and LINT green.

---

## Phase 4: HTML features (JS track)

### T15: Selection, neighbourhood focus, hover preview, detail pane
**Description:** The main way to cut clutter, and the main reading surface.

**Acceptance criteria:**
- [ ] Selecting a concept centres it, highlights exactly its N-hop neighbourhood (Hops control, 1–3) and fades the rest. Hover, selected and neighbourhood states are each visually distinct. Hovering shows the name, kind and first sentence of the definition without changing the selection.
- [ ] The detail pane shows:
  - the definition, set in a readable measure;
  - examples and non-examples, rules and open questions;
  - incoming and outgoing relations as links using inverse labels, with cardinality sentences in both directions;
  - `implemented_in` entries with their review commit and date, or "never reviewed";
  - section headings named after the concept schema's fields (Incoming relations and Findings for the sections that aren't fields);
  - a clearly marked "needs a definition" for `proposed` concepts, and agent suggestions visually separate and labelled.
- [ ] `graph-model.js` neighbourhood queries are tested via `page.evaluate`.

**Verification:** UI, LINT

**Dependencies:** T9

**Files:** `SK/assets/html/{app.js,graph-model.js,graph-view.js,app.css}`, `tests/test_html_ui.py`

**Scope:** M

### T16: Navigation, URL state, keyboard
**Description:** Exploration controls and shareable views.

**Acceptance criteria:**
- [ ] Pan, zoom (wheel and trackpad), fit-to-view, drag-to-pin and reset layout. Clicking a related concept moves the focus, and breadcrumbs step back.
- [ ] Deep links (`#id?hops=2&overlay=health`) restore the selection, hops and overlay on load and update as you navigate.
- [ ] Tab and arrow keys move between connected concepts, and Enter selects, with a visible focus ring using `--accent`.

**Verification:** UI, LINT

**Dependencies:** T15

**Files:** `SK/assets/html/{app.js,graph-view.js,app.css}`, `tests/test_html_ui.py`

**Scope:** M

### T17: Search with redirects
**Acceptance criteria:**
- [ ] `/` focuses search. Search matches names, discouraged terms and definition text. Arrow keys and Enter select a result, which moves the graph's focus to it.
- [ ] A discouraged term shows as a redirect ("'active user' → use **Active customer**"), ranked separately from direct matches.
- [ ] Results are ordered deterministically (exact name, then prefix, then term redirect, then definition text).

**Verification:** UI, LINT

**Dependencies:** T15

**Files:** `SK/assets/html/{app.js,app.css}`, `tests/test_html_ui.py`

**Scope:** S

### T18: Filters and list view
**Acceptance criteria:**
- [ ] Kind, status and relation-type filters apply to the graph and the list alike. Edges to hidden concepts are drawn as stubs.
- [ ] The list tab is a sortable table of all visible concepts. Its selection is shared with the graph and the detail pane.
- [ ] The list and detail views give complete non-visual access to everything in the graph: an accessibility smoke check of roles and labels.

**Verification:** UI, LINT

**Dependencies:** T15

**Files:** `SK/assets/html/{app.js,graph-model.js,graph-view.js,app.css}`, `tests/test_html_ui.py`

**Scope:** M

### T19: Finding badges, overlays, Health panel
**Acceptance criteria:**
- [ ] Concepts with findings show a severity badge (semantic colours, never kind colours). The detail pane lists their codes and criteria.
- [ ] The Health, Mud and Drift overlays highlight exactly the specified sets. The Mud overlay includes `related_to` and relations whose type is `proposed`.
- [ ] The Health panel groups findings by criterion. Clicking one focuses its concept.

**Verification:** UI (fixture build with known findings), LINT

**Dependencies:** T15 (finalise after T10–T13)

**Files:** `SK/assets/html/{app.js,graph-view.js,app.css}`, `tests/test_html_ui.py`

**Scope:** M

### T20: Vocabulary panel, legend, extension encodings
**Acceptance criteria:**
- [ ] The legend is always visible. Hovering an entry shows its definition.
- [ ] The Vocabulary panel lists core and extension kinds and relation types, with definition, status, `from`/`to` and usage counts. Clicking an entry filters the graph.
- [ ] Extension kinds get slots 5–8 and the remaining shapes by sorted id, stable across builds. A ninth or later kind uses the neutral fallback.

**Verification:** UI, LINT

**Dependencies:** T18 (finalise after T12)

**Files:** `SK/assets/html/{app.js,graph-view.js,app.css}`, `SK/scripts/ontokit/build.py` (encoding resolution), `tests/test_html_ui.py`

**Scope:** M

### T21: Hierarchy layout and semantic zoom
**Acceptance criteria:**
- [ ] The hierarchy toggle lays out the `acyclic` relation types (core and extension) top-down with a layered force. Concepts with several parents are placed sensibly. The layout is deterministic.
- [ ] When zoomed out, only labels of high-degree, selected or neighbourhood concepts are shown. Zooming in reveals all of them.
- [ ] Depth levels are computed in `graph-model.js` and tested via `page.evaluate` on a DAG with a diamond.

**Verification:** UI, LINT

**Dependencies:** T16

**Files:** `SK/assets/html/{graph-model.js,graph-view.js,app.js}`, `tests/test_html_ui.py`

**Scope:** M

### T22: Scale and design checks
**Acceptance criteria:**
- [ ] A deterministic generator creates `tests/fixtures/large` (300 concepts, 600 relations, realistic clustering). The first render is under 2 s in Playwright, and selection and zoom stay responsive.
- [ ] Token tests check:
  - WCAG contrast for every text/background pair (≥ 4.5:1) and for kind colours and boundaries (≥ 3:1), in both themes;
  - the kind palette stays distinguishable under protanopia, deuteranopia and tritanopia simulation (CIEDE2000 above a threshold).
- [ ] A raw-literal lint fails on any colour, size or spacing literal in `app.css` or the JS outside `tokens.css`. `prefers-reduced-motion` sets durations to 0, and dark mode follows `prefers-color-scheme` (Playwright emulation).

**Verification:** PYTEST (`tests/test_design_tokens.py`), UI

**Dependencies:** T21

**Files:** `tests/gen_large_fixture.py`, `tests/test_design_tokens.py`, `tests/test_html_ui.py`, `SK/assets/html/tokens.css` (if the checks force adjustments)

**Scope:** M

### Checkpoint 4: View complete (human review)
- [ ] UI fully green (all Playwright interaction tests in the spec).
- [ ] **Manual design review with you** against the five principles:
  - both themes;
  - 1280×720 and a large monitor;
  - reduced motion and colour-blind simulation;
  - the sample project and the 300-concept "structure, not a hairball" check.
- [ ] Success criteria 6, 7, 7a and 8 pass.

---

## Phase 5: Skill packaging

### T23: `init --agents-md` / `--gitattributes`
**Acceptance criteria:**
- [ ] `--agents-md` inserts the templated section between marker comments, creating `AGENTS.md` if needed. Re-running updates it in place without duplicating it, and leaves the rest of the file byte-identical.
- [ ] `--gitattributes` adds `docs/ontology/index.html -diff linguist-generated=true` once, idempotently. The `--no-*` flags and the absence of a flag change nothing.
- [ ] Both honour `--dry-run`.

**Verification:** PYTEST (`tests/test_init.py`), LINT

**Dependencies:** T3

**Files:** `SK/assets/templates/agents-md-section.md`, `SK/scripts/ontokit/init.py`, `tests/test_init.py`

**Scope:** S

### T24: `SKILL.md` body and `references/workflow.md`
**Acceptance criteria:**
- [ ] The `SKILL.md` body (under 500 lines and about 5k tokens) covers:
  - how to resolve `$SKILL`;
  - the hard rules near the top (authorship, canonical terms, consent, never run `review` unconfirmed);
  - the seven workflow steps, with exact commands;
  - gotchas (rebuild to resolve conflicts, stdin, exit codes);
  - "when to read" links to each reference.
- [ ] `workflow.md` details the proposal, review, health-check and conflict-resolution procedures, including cardinality suggestions with evidence.
- [ ] No harness-specific vocabulary. Instructions are phrased as actions any shell-capable agent can take.

**Verification:** Manually: read-through with you. Automated: the T26 lint once it exists.

**Dependencies:** CP3 (draft any time after CP1)

**Files:** `SK/SKILL.md`, `SK/references/workflow.md`

**Scope:** S–M

### T25: Remaining references
**Acceptance criteria:**
- [ ] `schema.md` covers every concept and manifest field, with the authorship and one-term rules.
- [ ] `vocabulary.md` covers the core meanings, when and how to extend the vocabulary, and how to challenge near-duplicates.
- [ ] `gruber-criteria.md` gives the five criteria, each with good and bad definition examples, and the cardinality-versus-table-grain note under minimal encoding bias. Each finding code maps to its criterion.
- [ ] References are one level deep and contain no onward links.

**Verification:** Manually: read-through. Automated: the T26 lint.

**Dependencies:** CP3

**Files:** `SK/references/{schema,vocabulary,gruber-criteria}.md`

**Scope:** S

### T26: Packaging, conformance and isolation tests
**Description:** Prove the copy-anywhere, harness-neutral, spec-conformant and isolation guarantees. **Asks you before downloading `skills-ref`.**

**Acceptance criteria:**
- [ ] Copy tests: copy `SK/` into differently nested locations in a temp project and run every command from the project root. A static scan finds no references outside `SK/`.
- [ ] Conformance tests:
  - `skills-ref validate` (pinned version) passes;
  - `SKILL.md` lint passes: body under 500 lines, references relative, resolving and one level deep, nothing from the harness-term denylist;
  - vendor integrity passes.
- [ ] Isolation test: running every command in a fixture project with its own `pyproject.toml`, `uv.lock` and `.venv` leaves them byte-identical.

**Verification:** PYTEST (`tests/test_packaging.py`, `tests/test_isolation.py`), LINT

**Dependencies:** T23, T24, T25

**Files:** `tests/test_packaging.py`, `tests/test_isolation.py`, `tests/fixtures/host-project/`

**Scope:** M

### Checkpoint 5: Packaged
- [ ] PYTEST, UI and LINT all green from a clean clone.
- [ ] Success criterion 9 passes.

---

## Phase 6: Acceptance

### T27: Cursor eval scenarios (human-run)
**Description:** You run scenarios (a)–(f) in `examples/sample-project` with the skill copied into Cursor's project skills folder. I prepare the script and fix the `SKILL.md`/reference wording based on what you see.

**Acceptance criteria:**
- [ ] `examples/evals.md` gives each scenario a setup, a prompt to give the agent, and explicit pass/fail expectations.
- [ ] All six scenarios pass in Cursor, including (b): the agent never authors a definition or sets `defined` on its own.
- [ ] Any failures lead to wording fixes and are re-run.

**Verification:** Manually, by you in Cursor. Results are recorded in `examples/evals.md`.

**Dependencies:** CP5

**Files:** `examples/evals.md`, `SK/SKILL.md`, `SK/references/*.md`

**Scope:** S

### Done
- [ ] Success criteria 1–10 met.
- [ ] `SK/` ready to copy into the agentic-toolkit repo, with `metadata.version` set to `1.0.0`.
