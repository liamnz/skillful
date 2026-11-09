# Tasks: `designing-the-architecture` skill

*Plan: [plan.md](plan.md). Spec: [SPEC.md](../../docs/architecture-skill/SPEC.md). `AK` = `skills/designing-the-architecture`. `OK` = `skills/curating-the-ontology`. `TA` = `tests/architecture`.*

**Standard verification commands**

```bash
uv run --with pytest --with pyyaml --with jsonschema pytest tests/architecture -q                        # PYTEST
uv run --with ruff ruff check . && uv run --with ruff ruff format --check .                              # LINT
uv run --with pytest --with pytest-playwright --with pyyaml --with jsonschema pytest tests/architecture -q   # UI (from A16)
uv run --with pytest --with pytest-playwright --with pyyaml --with jsonschema pytest tests/ -q           # ALL (Phase 0 uses this)
```

**Definition of done**
- Every task: PYTEST and LINT are green, and new behaviour has tests. Fixtures count as data, not toward the file limit.
- Every task touching the explorer: UI is also green.
- `AK/` references nothing outside itself and imports nothing from `OK/`.
- A new or changed finding code is updated in the `CODES` registry, the spec table and a fixture together.

---

## Phase 0: Repository reorganisation

### P0: Commit and merge the spec and plan
**Description:** Land the approved spec, intent and this plan on `main` so Phase 0 can branch from them.

**Acceptance criteria:**
- [x] `docs/architecture-skill/{SPEC,intent}.md` and `tasks/architecture/{plan,todo}.md` are committed on `docs/architecture-skill-spec`.
- [x] Approved spec changes (same-day replay, W114, Project Structure comment) are made and dated in the status line.
- [x] The branch is merged into `main` with `--no-ff` after your approval.

**Verification:** `git status` clean; `git log` shows the merge.

**Dependencies:** None. **Files:** those above. **Scope:** S

### R1: Move docs and tasks
**Description:** Give the ontology skill's docs and task records their own folders. First record the before-state of all tests.

**Acceptance criteria:**
- [x] Per-test results from ALL (490 collected) are saved outside the repo as the comparison baseline.
- [x] `docs/SPEC.md` → `docs/ontology-skill/SPEC.md`, `docs/intent/ontology-skill.md` → `docs/ontology-skill/intent.md`, `tasks/plan.md` and `todo.md` → `tasks/ontology/`, all with `git mv`.
- [x] The finding-coverage test's spec path and the ontology spec's links and Project Structure are updated. `tasks/ontology/` contents are unchanged.

**Verification:** ALL gives identical results; LINT; `git diff main -- OK/` empty.

**Dependencies:** P0. **Files:** the moved files, `tests/test_finding_coverage.py`, and any other test naming those paths. **Scope:** S

### R2: Move examples
**Description:** Move the ontology examples under `examples/ontology/`.

**Acceptance criteria:**
- [x] `sample-project/`, `design/`, `evals.md` and `evals/` are under `examples/ontology/` with `git mv`.
- [x] `SAMPLE` in tests and `REPO` in `setup_eval.py` (now one level deeper) resolve correctly, and `setup_eval.py a` works.
- [x] References in the ontology spec, `evals.md`, the sample README and the mockup caption are updated, and the sample's `index.html` is still current.

**Verification:** ALL identical to baseline; LINT; `git diff main -- OK/` empty.

**Dependencies:** R1. **Files:** moved files, `tests/conftest.py`, `examples/ontology/evals/setup_eval.py`, `evals.md`, README, ontology spec. **Scope:** M

### R3: Move tests and introduce `ontotest.py`
**Description:** Move all tests to `tests/ontology/` with the `test_onto_` prefix, and take shared helpers out of `conftest` so a second suite can't collide.

**Acceptance criteria:**
- [x] All of `tests/` moves to `tests/ontology/`, and each `test_<name>.py` becomes `test_onto_<name>.py`, with `git mv`.
- [x] Helpers and constants move from `conftest.py` to `ontotest.py`, all 25 importing modules use it, and `conftest.py` holds only pytest fixtures. `REPO` uses `parents[2]`.
- [x] `.gitignore`, usage comments and the ontology spec's Project Structure and Testing Strategy are updated. Running pytest with a throwaway `tests/architecture/conftest.py` beside it collects without conflict.

**Verification:** ALL gives the same 490 tests and outcomes (names mapped by prefix); golden regeneration gives no diff; LINT; `git diff main -- OK/` empty.

**Dependencies:** R2. **Files:** mechanical rename of the suite, `ontotest.py`, `conftest.py`, `.gitignore`, ontology spec. This task is larger than five files, but the only logic change is in `conftest.py` and `ontotest.py`. **Scope:** M

### R4: Rewrite `CLAUDE.md`
**Description:** Describe the repo as a home for several skills.

**Acceptance criteria:**
- [x] Shared conventions come first, followed by one section per skill. The ontology content is kept and its paths corrected.
- [x] Commands are given for one skill's tests and for all tests, and every command shown has been run.
- [x] The architecture section is a short stub pointing to its spec, and A33 completes it.

**Verification:** Run each command in `CLAUDE.md`; ALL identical to baseline.

**Dependencies:** R3. **Files:** `CLAUDE.md`. **Scope:** S

### R5: Rename the ontology page to "explorer"
**Description:** With two skills in one repo, "view" must mean only an architecture view. Starts only after the R1–R4 checks pass.

**Acceptance criteria:**
- [x] Wording that means the page is changed in `SKILL.md`, references, script help and messages, the ontology spec's "HTML view" section, `CLAUDE.md` and test comments. `SKILL.md` says "the ontology explorer" on first mention.
- [x] "Fit to view", the graph, list and hierarchy screens, `graph-view.js`, `build`, `index.html`, schemas and finding codes are unchanged.
- [x] `metadata.version` is `1.0.1`, the sample page and affected golden files are regenerated, and a dated amendment is recorded in the ontology spec.

**Verification:** ALL passes; the diff of `OK/` shows only wording and version; `build --check` passes on the sample project.

**Dependencies:** R4. **Files:** about 12 files in `OK/` with one-line wording edits, sample `index.html`, spec, `CLAUDE.md`. **Scope:** M

### Checkpoint 0
- [x] R1–R4 evidence shown: empty `OK/` diff, 490 tests, same outcomes.
- [x] R5 evidence shown: suite green, wording-only diff.
- [ ] You approve; `phase-0-repo-reorg` merged with `--no-ff`.

---

## Phase 1: Foundation

### A1: Walking skeleton
**Description:** A self-contained skill directory and a CLI shell that runs from any location.

**Acceptance criteria:**
- [ ] `--help` and `--version` work from the repo root and from a nested temp copy of `AK/`.
- [ ] All ten commands are registered with help text. An unimplemented one or a bad flag exits 2 with a clear message.
- [ ] `SKILL.md` has conforming frontmatter, using the spec's description, and `--version` reads its `metadata.version`.

**Verification:** PYTEST (`test_arch_cli.py`), LINT.

**Dependencies:** CP0. **Files:** `AK/SKILL.md`, `AK/scripts/arch.py`, `AK/scripts/archkit/{__init__,cli,findings}.py`, `TA/{conftest,archtest,test_arch_cli}.py`. **Scope:** M

### A2: Schemas, vocabulary, views, loader, `validate` (E001–E003)
**Description:** Define the record contracts and load a project into an immutable model.

**Acceptance criteria:**
- [ ] JSON Schemas cover the manifest, component, decision, view record and walkthrough, including all ten change operations. Each view's `facts` keys are enforced.
- [ ] `core-vocabulary.yaml` holds the six kinds and three connections. `core-views.yaml` defines all nine views in the standard shape.
- [ ] A baseline fixture yields no findings and exit 0. E001, E002 and E003 fixtures each yield exactly that code and exit 1.

**Verification:** PYTEST (`test_arch_validate.py`, `test_arch_views.py`), LINT.

**Dependencies:** A1. **Files:** `AK/assets/schemas/*`, `AK/scripts/archkit/{io,schema,checks}.py`, `TA/test_arch_*.py`, `TA/fixtures/`. **Scope:** M

### A3: `init`
**Description:** Scaffold `docs/architecture/`.

**Acceptance criteria:**
- [ ] In an empty git repo, `init` creates the layout with every optional view `undecided`, and `validate` exits 0 with no warnings (SC1).
- [ ] Re-running leaves files byte-identical. `--dry-run` writes nothing and lists planned writes.
- [ ] `--spec` paths are recorded, and without the `AGENTS.md` flags a one-line hint goes to stderr.

**Verification:** PYTEST (`test_arch_init.py`), LINT.

**Dependencies:** A2. **Files:** `AK/assets/templates/*`, `AK/scripts/archkit/init.py`, `cli.py`, test. **Scope:** S

### A4: Apply engine and replay (components, connections, vocabulary)
**Description:** The pure core: apply a list of changes to a target, or refuse. Includes replay in the order from plan Decision 3.

**Acceptance criteria:**
- [ ] `add_component`, `update_component`, `retire_component`, `add_connection`, `remove_connection` and `add_vocabulary` work, set `decided_by` themselves, and raise `ChangeConflict` on an invalid change.
- [ ] Applying is pure: on failure the input target is unchanged.
- [ ] Replay yields the current target for fixtures, including a same-day decision whose id sorts before one it depends on.

**Verification:** PYTEST (`test_arch_apply.py`), LINT.

**Dependencies:** A2. **Files:** `AK/scripts/archkit/apply.py`, test. **Scope:** M

### A5: Apply engine (view entries and status)
**Description:** Extend apply to the views.

**Acceptance criteria:**
- [ ] `add_entry`, `update_entry`, `remove_entry` and `set_view_status` work, and a `not_needed` status must carry a reason.
- [ ] Target-side changes can alter `statement`, `components` and `title`. `facts` keys are checked per view.
- [ ] A mixed decision across components and views replays correctly.

**Verification:** PYTEST (`test_arch_apply.py`), LINT.

**Dependencies:** A4. **Files:** `apply.py`, test. **Scope:** S

### A6: `propose` and `accept`
**Description:** The one path into the target, with the canonical writer and atomic multi-file update.

**Acceptance criteria:**
- [ ] `propose` creates a `proposed` decision from a YAML file, and the target is unchanged. E008 fires when its changes can't apply.
- [ ] `accept` exits 3 and changes nothing on an empty or too-short why or a conflict. Otherwise it records the why verbatim, sets `accepted_on`, handles `supersedes`, and applies atomically (injected-failure test). E006 and E007 are covered by fixtures.
- [ ] Render → parse → render is byte-identical for every record type, and no command can rewrite an accepted decision apart from `status` and `superseded_by`.

**Verification:** PYTEST (`test_arch_decisions.py`), LINT.

**Dependencies:** A3, A5. **Files:** `AK/scripts/archkit/{decisions,records}.py`, `cli.py`, `checks.py`, test. **Scope:** M

### A7: `withdraw`, `component`, `entry`, `show`
**Description:** The remaining record commands, and the guards around agent-maintained fields.

**Acceptance criteria:**
- [ ] `withdraw` records the reason and works only on proposed decisions.
- [ ] `component` can change only `build`, `owns` and `notes`. `entry` can change only allowed `facts`. Attempts to change anything else are rejected.
- [ ] `show [--view] [--json]` gives the compact target, and `--dry-run` is honoured by every write command.

**Verification:** PYTEST (`test_arch_commands.py`, round-trip test), LINT.

**Dependencies:** A6. **Files:** `AK/scripts/archkit/{maintain,show}.py`, `cli.py`, tests. **Scope:** M

### Checkpoint 1
- [ ] `init → propose → accept → validate → show` round trip passes in a temp git repo.
- [ ] Review the record format and CLI output together.

---

## Phase 2: Risk first

### A8: Ownership, Python imports, state derivation
**Description:** Compare the target with Python code, and derive each component's state.

**Acceptance criteria:**
- [ ] `codemap` resolves globs and absolute and relative imports, using POSIX paths. W103, W104, W105, W106, W111 and I202 have fixtures. A connection in either direction permits a dependency.
- [ ] State follows the precedence order, including `partial` with no departures (on target) and `built` with no code (absent, plus W104).
- [ ] Unowned code and retired-but-owning components are reported as project-level departures.

**Verification:** PYTEST (`test_arch_codemap.py`, `test_arch_state.py`), LINT.

**Dependencies:** CP1. **Files:** `AK/scripts/archkit/{codemap,state}.py`, `checks.py`, tests. **Scope:** M

### A9: dbt reference reader and hybrid projects
**Description:** Read `ref()` and `source()` without running dbt.

**Acceptance criteria:**
- [ ] Each `dbt_project.yml` gives model, seed and snapshot paths, including custom paths. SQL comments are removed before reading, and Python models are read with `ast`.
- [ ] `ref()` resolves to the file of that name and `source()` to the declaring YAML. dbt package references and `target/manifest.json` are ignored.
- [ ] W105 fires across components in dbt and hybrid temp projects, with no dbt installed.

**Verification:** PYTEST (`test_arch_dbt.py`), LINT.

**Dependencies:** A8. **Files:** `AK/scripts/archkit/dbtrefs.py`, `codemap.py`, test. **Scope:** M

### A10: Git layer, W107, W110
**Description:** Git-based checks, with graceful fallback.

**Acceptance criteria:**
- [ ] W107 fires for changed target fields or `statement` with no decision change in the commit, including uncommitted changes, and never for agent-maintained fields.
- [ ] W110 fires after `stale_proposal_days`.
- [ ] Outside git both are skipped with an info notice, and only `gitinfo.py` shells out to git.

**Verification:** PYTEST (`test_arch_git.py`, temp repos), LINT.

**Dependencies:** A7. **Files:** `AK/scripts/archkit/{gitinfo,context}.py`, `checks.py`, test. **Scope:** M

### A11: `impact`
**Description:** The merge-checkpoint report.

**Acceptance criteria:**
- [ ] Reports touched components, unowned changes, undeclared dependencies and open proposals, including uncommitted changes (SC4).
- [ ] `--base` and `--json` work, with deterministic ordering.
- [ ] Works on Python, dbt and hybrid temp repos.

**Verification:** PYTEST (`test_arch_impact.py`), LINT.

**Dependencies:** A9, A10. **Files:** `AK/scripts/archkit/impact.py`, `cli.py`, test. **Scope:** S

### Checkpoint 2
- [ ] SC4 passes, and you've seen an `impact` report on a hybrid project.

### A12: Analysis example
**Description:** The small end of the range.

**Acceptance criteria:**
- [ ] `examples/architecture/analysis/` has at most five components and two decisions, and unused views are `not_needed` with reasons.
- [ ] Each `why` is written by you, per plan open question 3.
- [ ] Its findings match a committed expected-findings file.

**Verification:** PYTEST (`test_arch_examples.py`), LINT.

**Dependencies:** CP1. **Files:** example records and small code, test. **Scope:** M

### A13: Hybrid pipeline example
**Description:** The full workflow and every view, in Python and dbt.

**Acceptance criteria:**
- [ ] `examples/architecture/pipeline/` uses all nine views, with a walkthrough, an open proposal and a superseded decision.
- [ ] It contains a deliberate boundary crossing, with a note that it must stay, for eval (e) and off-target display.
- [ ] Each `why` is yours, and findings match the expected file.

**Verification:** PYTEST (`test_arch_examples.py`), LINT.

**Dependencies:** A12, A9. **Files:** example records and code. **Scope:** M

### A14: Design tokens and mockup (human gate)
**Description:** Agree how it looks before building it.

**Acceptance criteria:**
- [ ] `examples/architecture/design/mockup.html` shows the map, at least two views on it, a component detail, a decision, a history step and a proposal preview, in both themes, using the pipeline example's content.
- [ ] `AK/assets/html/tokens.css` is the only home of raw style values.
- [ ] **You approve the mockup.**

**Verification:** Reviewed in browser with you; contrast token test passes.

**Dependencies:** A13. **Files:** mockup, `tokens.css`, token test. **Scope:** M

### A15: Vendored D3, build pipeline, data contract, W108
**Description:** One self-contained page assembled deterministically.

**Acceptance criteria:**
- [ ] D3 modules are copied at the sibling's pinned versions, with `MANIFEST.json` checksums tested.
- [ ] `build` fills the template with the plan's data contract, including replay snapshots. Two builds are byte-identical, and git-based findings are excluded.
- [ ] `build --check` and W108 detect stale pages and ignore CRLF differences.

**Verification:** PYTEST (`test_arch_build.py`), LINT.

**Dependencies:** A11. **Files:** `AK/assets/vendor/*`, `AK/assets/html/index.html`, `AK/scripts/archkit/build.py`, test. **Scope:** M

### A16: Deterministic map render
**Description:** Components as boxes, in a seeded left-to-right layered layout.

**Acceptance criteria:**
- [ ] Kind, build status and off-target badge are encoded as specified. Absent components have no badge.
- [ ] Groups are quiet enclosures. Cycles and `calls` edges place cleanly.
- [ ] Positions are identical across loads, with no console errors from `file://` under the CSP.

**Verification:** UI (`test_arch_html_map.py`); compare with the mockup.

**Dependencies:** A14, A15. **Files:** `AK/assets/html/{map-model,map-view,app}.js`, `app.css`, test. **Scope:** M

### Checkpoint 3
- [ ] Pipeline map renders from `file://` as the mockup shows. Review it together.

---

## Phase 3: Validator completion

### A17: Reference and integrity errors
**Acceptance criteria:**
- [ ] E004, E005 and E009–E013 each have a fixture producing exactly that code.
- [ ] Extensions are usable once declared through `add_vocabulary`, and can't reuse core ids.
- [ ] The baseline stays clean.

**Description:** The remaining errors. **Verification:** PYTEST (`test_arch_checks.py`), LINT.

**Dependencies:** A6. **Files:** `checks.py` (split if large), test, fixtures. **Scope:** M

### A18: Warnings and info
**Acceptance criteria:**
- [ ] W101, W102, W109, W112, W113, W114, I201 and I203–I205 each have a fixture.
- [ ] W102 follows plan Decision 9, with tests for both thresholds and for a genuine why that doesn't fire.
- [ ] W114 fires when a target field or `statement` differs from replay, works without git, and ignores agent-maintained fields.

**Description:** The remaining advisory checks. **Verification:** PYTEST (`test_arch_checks.py`), LINT.

**Dependencies:** A17. **Files:** `checks.py`, test, fixtures. **Scope:** M

### A19: CLI hardening and coverage
**Acceptance criteria:**
- [ ] `--strict`, `--limit`, exit codes 0–4, stdout/stderr separation and never-interactive behaviour are tested on every command.
- [ ] Golden JSON covers `validate`, `show` and `impact`.
- [ ] `test_arch_finding_coverage.py` keeps the spec table, `CODES` and fixtures in sync.

**Description:** Make the conventions hold across the CLI. **Verification:** PYTEST, LINT.

**Dependencies:** A18, A11. **Files:** `cli.py`, `TA/test_arch_{conventions,finding_coverage}.py`, `TA/golden/`. **Scope:** M

### Checkpoint 4
- [ ] Every finding code has a fixture and the baseline is clean. SC1–4 pass.

---

## Phase 4: Explorer features

Each task: UI test file `TA/test_arch_html_<feature>.py`, plus `AK/assets/html/{app,pane}.js` and `app.css`.

### A20: Selection, component detail, navigation
**Acceptance criteria:**
- [ ] Clicking a component shows responsibility, connections in sentences, owned paths, build status, findings and shaping decisions, each with its human why first.
- [ ] Pan, zoom and fit work, and all interactions have keyboard access.
- [ ] Deep links restore the selection and view.

**Dependencies:** CP3. **Verification:** UI, LINT. **Scope:** M

### A21: View switcher
**Acceptance criteria:**
- [ ] One control lists all nine views with their questions, and `not_needed` views are muted with their reason.
- [ ] Each view recolours or annotates the map as in the spec's table.
- [ ] Positions are identical across all nine views (plan Decision 11).

**Dependencies:** A20. **Verification:** UI, LINT. **Scope:** M

### A22: View entries
**Acceptance criteria:**
- [ ] A stored view's panel lists entries, with agreed statements shown separately from agent-maintained facts.
- [ ] Selecting an entry highlights its components.
- [ ] Component detail lists its entries from each view in use.

**Dependencies:** A21. **Verification:** UI, LINT. **Scope:** S

### A23: Decisions timeline
**Acceptance criteria:**
- [ ] Newest first, by the replay order, with the why prominent.
- [ ] Options, trade-offs and consequences appear beneath and are labelled agent-drafted.
- [ ] The Decisions view highlights the components a decision shaped.

**Dependencies:** A20. **Verification:** UI, LINT. **Scope:** S

### A24: History
**Acceptance criteria:**
- [ ] Stepping shows the map after each accepted decision, from embedded snapshots.
- [ ] Later components are absent from earlier steps, and components keep their positions.
- [ ] The final step matches the current target.

**Dependencies:** A23. **Verification:** UI, LINT. **Scope:** M

### A25: Proposal preview
**Acceptance criteria:**
- [ ] An open proposal overlays additions, changes and retirements, using more than colour.
- [ ] Turning the preview off restores the map exactly.
- [ ] A proposal that can't apply is reported, not drawn.

**Dependencies:** A24. **Verification:** UI, LINT. **Scope:** M

### A26: Walkthroughs
**Acceptance criteria:**
- [ ] Choosing one highlights its path and steps through it, one component at a time.
- [ ] Situation, outcome and open concerns are shown.
- [ ] Works by keyboard and from a deep link.

**Dependencies:** A21. **Verification:** UI, LINT. **Scope:** S

### A27: Progress
**Acceptance criteria:**
- [ ] Counts on target, off target and absent, plus project-level departures, matching the CLI's derived states.
- [ ] Each count filters the map.
- [ ] Wording never implies that on target means verified.

**Dependencies:** A20. **Verification:** UI, LINT. **Scope:** S

### A28: Scale and design checks
**Acceptance criteria:**
- [ ] A 15-component project and a 40-component stress fixture render within budget.
- [ ] Contrast and colour-blind token tests pass in both themes, along with the raw-literal lint.
- [ ] No network access occurs, and output is reproducible across working directories.

**Dependencies:** A21–A27. **Verification:** UI, LINT. **Files:** tests, fixture generator. **Scope:** M

### Checkpoint 5
- [ ] Manual design review with you, against the ontology spec's design principles, in both themes, at 1280×720 and large, with colour-blind simulation. SC5 passes.

---

## Phase 5: Skill packaging

### A29: `init --agents-md` and `--gitattributes`
**Acceptance criteria:**
- [ ] With consent, a marked section makes both checkpoints always-on, and nothing outside it changes.
- [ ] Re-running is idempotent, and `--no-` flags write nothing.
- [ ] `--gitattributes` marks `index.html` as generated.

**Dependencies:** A3. **Verification:** PYTEST (`test_arch_init.py`), LINT. **Files:** `init.py`, templates, test. **Scope:** S

### A30: `SKILL.md` body
**Acceptance criteria:**
- [ ] "Hard rules" comes first, with the human-why rule and the "never" list.
- [ ] Covers the nine workflow steps, including how to ask for a why without offering wording, and the surprise test.
- [ ] Under 500 lines and about 3,800 words, using no harness-specific terms.

**Dependencies:** CP4. **Verification:** PYTEST (packaging checks), LINT. **Files:** `AK/SKILL.md`. **Scope:** M

### A31: References: schema, vocabulary, views
**Acceptance criteria:**
- [ ] `schema.md` matches the JSON Schemas, and every code appears under the right heading.
- [ ] `vocabulary.md` gives analysis and pipeline examples of each term.
- [ ] `views.md` gives each view's questions, drawn from `core-views.yaml`, and each file has a "read when" trigger.

**Dependencies:** A30. **Verification:** PYTEST (packaging). **Files:** `AK/references/*`. **Scope:** M

### A32: References: concepts, proposals, worked examples
**Acceptance criteria:**
- [ ] `concepts.md` explains views, C4 and how its "component" differs, ADRs, reflexion and quality scenarios in plain language.
- [ ] `proposals.md` covers good trade-offs and a before-and-after.
- [ ] `examples.md` shows both ends of the size range, written fresh and not linking outside the skill.

**Dependencies:** A30. **Verification:** PYTEST (packaging). **Files:** `AK/references/*`. **Scope:** M

### A33: Packaging and isolation tests, `CLAUDE.md`
**Acceptance criteria:**
- [ ] The skill passes the Agent Skills validator, the denylist, and all `SKILL.md` limits, and runs when copied anywhere.
- [ ] A test proves no import or path reference to `curating-the-ontology`, and a target project's Python environment is untouched.
- [ ] `CLAUDE.md`'s architecture section is complete, and ALL is green from a clean clone.

**Dependencies:** A29, A31, A32. **Verification:** ALL, LINT. **Files:** `TA/test_arch_{packaging,isolation}.py`, `CLAUDE.md`. **Scope:** M

### Checkpoint 6
- [ ] SC6, SC7 and SC7a pass.

---

## Phase 6: Acceptance

### A34: Eval scenarios
**Acceptance criteria:**
- [ ] `examples/architecture/evals.md` gives scenarios (a)–(h) with explicit pass and fail expectations.
- [ ] `evals/setup_eval.py <letter>` creates a fresh project for each one.
- [ ] A test confirms each setup runs.

**Dependencies:** CP6. **Verification:** PYTEST, LINT. **Files:** `examples/architecture/evals*`, test. **Scope:** M

### A35: Cursor eval runs (human-run)
**Acceptance criteria:**
- [ ] All eight scenarios pass in Cursor, including (a): the agent never records a why you didn't give.
- [ ] Failures lead to wording fixes and are re-run.

**Dependencies:** A34. **Verification:** You run them and record the results. **Scope:** S

### A36: Release
**Acceptance criteria:**
- [ ] `metadata.version` is `1.0.0`, and the example pages and golden output are regenerated.
- [ ] ALL and LINT are green from a clean clone, and SC1–8 are met.

**Dependencies:** A35. **Verification:** ALL, LINT. **Scope:** S

### Done
- [ ] Success criteria 1–8 met. The skill directory is ready to copy into the agentic-toolkit repo.
