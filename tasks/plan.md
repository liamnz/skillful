# Implementation Plan: `curating-the-ontology` skill

*Source: [docs/SPEC.md](../docs/SPEC.md) (approved 2026-11-08). Tasks: [tasks/todo.md](todo.md).*

## Overview

We're building a self-contained Agent Skill in `skills/curating-the-ontology/` with four parts:

- **CLI:** a PEP 723 Python CLI (`onto.py`) that scaffolds, creates, validates and builds YAML concept records.
- **Validator:** checks with stable finding codes, including git-based drift detection.
- **HTML view:** a self-contained, deterministic page that leads with an interactive graph (vendored D3).
- **Agent instructions:** `SKILL.md` and `references/`, which teach any coding agent the human-owned curation workflow.

The work is sliced so that there is a working end-to-end path (`init → new → validate → build → open the page`) early on. The riskiest pieces are tackled first: W106 drift, D3 vendoring and determinism, and the design gate.

## Architecture decisions

1. **The entry point puts its own directory on the import path.** `onto.py` adds its own directory to `sys.path` and imports `ontokit`. `ontokit` finds `assets/` via `Path(__file__)`. Nothing depends on cwd or on install location. The packaging test checks this from the first task, not only at the end.
2. **Comment-preserving writes.** PyYAML drops comments and reflows text when it rewrites a file. Every command that *changes* an existing human-edited file (`review` → `reviewed_at`, `vocab new` → `ontology.yaml`) therefore makes a targeted text edit, never a load/dump round trip. Each such edit is verified by re-parsing the file. Commands that create new files (`new`, `init`) render them from templates.
3. **Checks are pure functions over a loaded model.** `io.py` builds an immutable model (manifest, vocabulary, concepts, source locations). `gitinfo.py` is the only module that shells out to git. `checks.py` (split into a package if it grows) returns sorted `Finding`s, and the CLI is the only place that formats output.
4. **One build data contract, defined before any UI work.** `build` embeds one JSON blob in `index.html`:
   - `schemaVersion`, `skillVersion`, `inputHash`;
   - the manifest and the resolved vocabulary (core + extensions, with their visual encodings);
   - the concepts;
   - the findings (every check except W108, which is about the HTML itself);
   - per-path git review info (commit and date).

   The HTML tasks code against this contract, so the JS track and the Python track can proceed in parallel.
5. **The staleness hash ignores line endings.** `inputHash` is a SHA-256 of a canonical JSON serialisation of the *parsed* records plus the skill version, not of raw bytes. Windows checkouts with `core.autocrlf` (as on this machine) then don't make `build --check` or W108 report a stale file. The output is written with LF endings, and a test asserts that it's byte-identical whatever the working directory.
6. **Reproducibility at a given commit.** Embedded findings and review dates come from git. A build is byte-identical for the same records *and* the same git state, which matches the spec's "two people building from the same records". A test pins this.
7. **Pure JS is tested in the browser, without Node.** `graph-model.js` exposes its pure functions on a namespace. Playwright tests call them via `page.evaluate`. No npm, in line with the spec.
8. **Deterministic layout:**
   - a seeded PRNG (e.g. mulberry32 hashed from the concept id) gives the initial positions and `simulation.randomSource()`;
   - a fixed tick count runs synchronously before the first render;
   - Playwright asserts identical positions across loads.
9. **Design tokens first.** `tokens.css` is created at the mockup gate. Later CSS uses only tokens, and a raw-literal lint enforces that from Task 22.

## Dependency graph

```
T1 skeleton ──► T2 schemas+loader+validate ──┬─► T3 init ──► T4 new ──► [CP1]
                                             │
         ┌───────────────────────────────────┴───────────────────────┐
         ▼                                   ▼                       ▼
   T5 git + W106 + review           T6 sample project        T8 vendor D3 + build pipeline
         │                                   │                       │
         │                                   ▼                       │
         │                          T7 tokens + mockup ◄─────────────┘ (gate: human approval)
         │                                   │
         │                                   ▼
         │                          T9 deterministic graph render ──► [CP2]
         ▼                                   │
 Python track (after CP1):            JS track (after CP2):
  T10 relation checks                   T15 selection + detail pane
  T11 term/definition checks            T16 navigation + URL + keyboard
  T12 vocab extensions + commands       T17 search + redirects
  T13 files, staleness, impact          T18 filters + list view
  T14 CLI conventions hardening         T19 findings, overlays, health panel  (needs T10–T13)
         │                              T20 vocabulary panel + legend         (needs T12)
         ▼                              T21 hierarchy + semantic zoom
       [CP3]                            T22 scale + design checks ──► [CP4: manual design review]
                                             │
 Docs track (any time after CP1; finalise after CP3):
  T24 SKILL.md + workflow.md, T25 other references
                                             ▼
 T23 init --agents-md/--gitattributes ──► T26 packaging + isolation tests ──► [CP5]
                                             ▼
                               T27 Cursor eval scenarios (human-run) ──► [Done]
```

## Task list

### Phase 1: Foundation
- [x] T1: Walking skeleton (skill dir, CLI shell, Finding, dev config)
- [x] T2: Schemas, core vocabulary, loader and `validate` (E001–E003)
- [x] T3: `init` (manifest template with commented-out starter extensions)
- [x] T4: `new` (proposed stubs)

**Checkpoint 1 (passed 2026-11-08):** `init → new → validate` round trip works in a temp git repo. pytest and ruff are green.

### Phase 2: Risk first (drift, build pipeline, design gate)
- [x] T5: Git layer, W106 drift, `review`, I205
- [x] T6: Sample project (`examples/sample-project`)
- [x] T7: Design tokens and static mockup. **Human gate: approved 2026-11-08** after review rounds: labelled edges, boxed concepts, schema-worded pane headings, no mini-graph, Hops control, symbol badges.
- [x] T8: Vendor D3 and the build pipeline (`build`, `--check`, W108, data contract). D3 pinned to the 2021–22 releases: the 3 Nov 2026 patch releases were skipped as too new to trust yet (source unchanged; tooling-only).
- [x] T9: Deterministic graph render (force layout, kind/status/relation encoding)

**Checkpoint 2 (passed 2026-11-09):** W106 behaves as specified in temp repos. The sample project's graph renders from `file://` the way the approved mockup shows it. Review it together.

### Phase 3: Validator completion (Python track)
- [x] T10: Relation checks (E004, E006, E013, E014, W104, W111, I204)
- [x] T11: Term and definition checks (E007, E008, W101, W102, W103, W109, I201, I202)
- [x] T12: Vocabulary extensions: checks (E005, E010–E012, W110, W112, W113, I203) and the `vocab new`/`vocab list` commands
- [x] T13: Filesystem, staleness and `impact` (E009, W105, W107)
- [x] T14: CLI conventions hardening (`--strict`, `--limit`, golden JSON, exit codes, `schema_version`)

**Checkpoint 3 (passed 2026-11-09):** every finding code has a fixture, and the baseline is clean. Success criteria 1–5a pass.

### Phase 4: HTML features (JS track)
- [x] T15: Selection, neighbourhood focus, hover preview, detail pane
- [x] T16: Navigation: pan/zoom/fit/pin, breadcrumbs, URL deep links, keyboard
- [x] T17: Search with redirects
- [x] T18: Filters and list view
- [x] T19: Finding badges, Health/Mud/Drift overlays, Health panel
- [x] T20: Vocabulary panel, legend definitions, extension encodings
- [x] T21: Hierarchy layout (layered force) and semantic zoom
- [x] T22: Scale and design checks (300-concept fixture, performance, contrast, colour-blind, raw-literal lint)

**Checkpoint 4 (passed 2026-11-09, after adding quick filter choices):** manual design review against the five principles:
- both themes;
- 1280×720 and a large monitor;
- reduced motion and colour-blind simulation;
- the 300-concept "structure, not a hairball" check.

Success criteria 6–8 pass.

### Phase 5: Skill packaging
- [x] T23: `init --agents-md` / `--gitattributes`
- [x] T24: `SKILL.md` body and `references/workflow.md`
- [x] T25: `references/schema.md`, `vocabulary.md`, `gruber-criteria.md`
- [x] T26: Packaging, conformance and isolation tests

**Checkpoint 5 (passed 2026-11-09; 490 tests green from a clean clone):** the full automated suite is green. Success criterion 9 passes.

### Phase 6: Acceptance
- [ ] T27: Cursor eval scenarios (a)–(f), run by you in `examples/sample-project`

**Done:** success criteria 1–10 met. The skill directory is ready to copy into the agentic-toolkit repo.

## Parallelisation

- After CP1, the **Python track** (T5, T10–T14) and the **design/JS track** (T6–T9, then T15–T22) touch disjoint files and can run in separate sessions.
- The design gate (T7) blocks only the JS track. Python work continues while you review the mockup.
- T19 and T20 consume findings and vocabulary from the Python track. They can start against the data contract with fixture data and be finished once T10–T13 land.
- The docs (T24, T25) can be drafted any time after CP1. They're finalised after CP3, when command behaviour is settled.
- The sequential spine: T1 → T2 → (T3, T4), and T8 → T9.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| W106 is noisy or misses changes (hunk-to-symbol proximity, renames, uncommitted changes, Windows paths) | High | Built in Phase 2 against the six specified temp-repo cases before anything depends on it. Proximity is computed on both sides of each hunk. |
| A PyYAML round trip destroys human formatting and comments in records | High | Decision 2: targeted text edits plus a re-parse check. Each writer has tests asserting the rest of the file is byte-identical. |
| D3 UMD concatenation order or globals break offline inlining | Medium | Pinned versions with order recorded in `MANIFEST.json`. A static test and a Playwright test check for zero console errors from `file://` with network access blocked. |
| Non-deterministic layout (floating-point quirks, iteration order) | Medium | Seeded PRNG, sorted inputs, a fixed tick count. Two-load position equality is tested in T9 and re-run in CI-style local suites. |
| CRLF checkouts make `build --check` / W108 report false staleness | Medium | Decision 5: the hash covers parsed content. Tests cover a CRLF copy of the fixtures. |
| A 300-concept graph is an unreadable hairball or slower than 2 s | Medium | Semantic zoom and focus (T21, T15). The large fixture and a performance test land in T22, with a human hairball check at CP4. If it's too slow, tune the tick count and alpha decay first. |
| The design churns after implementation starts | Medium | Mockup gate (T7) before any view code. Feedback goes into tokens and the spec, not ad hoc CSS. |
| `skills-ref` availability, version or invocation unclear | Low | Pin the version and resolve the exact invocation in T26. If unavailable, record it and fall back to our own frontmatter lint (already specified). |
| Downloads needed (D3 modules, Playwright Chromium, `skills-ref`) | Low | I ask you before each download, giving the name, source and size. Checksums are recorded for D3. |
| Agent behaviour in Cursor differs from the instructions | Medium | T27 scenarios with explicit pass/fail expectations, and iteration on `SKILL.md` wording. Hard rules sit near the top of `SKILL.md`. |

## Human touchpoints

- **T7:** approve the design mockup. This blocks the view work.
- **Checkpoint 2:** look at the first rendered graph.
- **Checkpoint 4:** manual design review.
- **T27:** run the Cursor scenarios.
- **Downloads:** approve each one when it comes up (T8, T9, T26).

## Working conventions

- **Branching:**
  - Each phase gets its own branch off `main` (e.g. `phase-1-foundation`, `phase-2-risk-first`). With parallel tracks, each track gets its own branch.
  - One commit per task, with a conventional message that names the task id (e.g. `feat(cli): T4 add new command`).
  - The branch is merged into `main` with `--no-ff` once its checkpoint passes and you've approved it. `main` always stays green.
  - Nothing is pushed until a remote exists and you ask.
- **Sample domain:** the generic e-commerce/subscription domain from the spec ("Acme": customers, orders, subscriptions, retention). It's used for `examples/sample-project`, the mockup and the Cursor evals.

## Open questions

1. ~~**Commit workflow.**~~ **Resolved:** branch per phase, as described under Working conventions.
2. ~~**Sample project domain.**~~ **Resolved:** the generic e-commerce domain.
