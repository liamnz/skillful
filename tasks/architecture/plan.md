# Implementation Plan: `designing-the-architecture` skill

*Source: [SPEC.md](../../docs/architecture-skill/SPEC.md) (approved 2026-11-10). Tasks: [todo.md](todo.md). Status: APPROVED 2026-11-10.*

## Overview

Two pieces of work, in order:

1. **Phase 0** reorganises the repo so both skills are equals, and is merged on its own.
2. **Phases 1–6** build a self-contained skill in `skills/designing-the-architecture/`:
   - **CLI:** `arch.py` over `archkit`, which records a target architecture and changes it only through accepted decisions.
   - **Code comparison:** derives on target, off target and absent from Python imports and dbt references.
   - **Explorer:** a self-contained page showing nine views on one map, with history and proposal preview.
   - **Agent instructions:** `SKILL.md` and `references/`, which teach the two checkpoints and the human-why rule.

The riskiest pieces come first: the apply and replay engine, the dbt reader, and the mockup gate. A working `init → propose → accept → validate` path exists by Checkpoint 1.

## Architecture decisions

These settle things the spec leaves to implementation.

1. **`archkit` follows `ontokit`'s layout, by copying and never importing.** The entry point puts its own directory on the path, assets are found through `__file__`, `cli.py` only dispatches, checks are pure and registered in `CHECKS`, and git goes only through `gitinfo.py`.
2. **Records are tool-owned, so one canonical writer serialises them.** The ontology skill needs targeted text edits because humans edit its YAML. Here target fields must never be hand-edited, so every write goes through a single renderer with fixed key order and block style. `propose` normalises the agent's YAML. Comments in records are not preserved, and the templates carry none. A test asserts render → parse → render is byte-identical.
3. **Replay order: `accepted_on`, then id, with dependencies respected within a day.** Strict date-then-id order breaks on a real case: `add-export-step` accepted the same day as `initial-target` sorts first and can't be applied. Within one date, replay repeatedly takes the lowest id that applies cleanly. `initial-target` is always first. This needs no schema change and stays deterministic.
4. **One pure apply engine.** `apply_changes` is used by `accept`, E008, proposal preview and history. It sets `decided_by` itself, so a proposal can't claim authority it lacks.
5. **Multi-file accept is all-or-nothing.** The new target is computed in memory, written to temporary files beside the targets, then swapped in with `os.replace`. If a swap fails, the originals are restored from backups. A test injects a failure midway.
6. **`codemap.py` is the single source of file-level dependencies.** It returns `(from_file, to_file, evidence)` for Python and dbt alike. Component states, W105 and `impact` are computed from it, so they can't disagree. It uses POSIX relative paths on every platform.
7. **State derivation is one pure function,** following the spec's precedence, and is the only source of states for the CLI and the explorer.
8. **One build data contract, defined before UI work.** `build` embeds manifest, resolved vocabulary and views, components, decisions, entries, walkthroughs, derived states, findings (records and working tree only), one replayed snapshot per accepted decision, and `inputHash`. The hash covers parsed records plus skill version, so CRLF checkouts don't report stale pages.
9. **W102 is a text-similarity rule with fixed thresholds.** It fires if the why shares a run of six or more words with `context`, `options`, or `consequences`, or if at least 70% of its content words come from them. It is advisory only, and the thresholds are constants with tests.
10. **W107 compares parsed fields, not text.** For each commit touching `components/` or `views/`, it parses before and after, and fires only when target fields or a `statement` changed and no file in `decisions/` changed in that commit. The working tree counts as a final pseudo-commit. Agent-maintained changes never fire it.
11. **The map layout never reads the active view.** Positions are computed once from components and `feeds`, seeded, with a fixed tick count. Browser tests assert identical positions across all nine views.
12. **D3 and the design base are copied from the sibling at its pinned versions.** No download or upgrade is involved. This skill keeps its own `MANIFEST.json` and `tokens.css`.

## Dependency graph

```
P0 commit spec + plan ──► R1 docs/tasks ──► R2 examples ──► R3 tests ──► R4 CLAUDE.md ──► R5 explorer wording ──► [CP0: merge]
                                                                                                                     │
A1 skeleton ──► A2 schemas+loader ──► A3 init ──► A4 apply engine ──► A5 view ops ──► A6 propose/accept ◄────────────┘
                                                                                          │
                                                                     A7 withdraw, component, entry, show ──► [CP1]
                                                                                          │
              ┌───────────────────────────────────────────┬───────────────────────────────┤
              ▼                                           ▼                               ▼
   A8 ownership+Python+states                     A12 analysis example             A15 vendor + build
              │                                   A13 pipeline example                    ▲
   A9 dbt reader                                          │                               │
              │                                           ▼                               │
   A10 git, W107, W110                            A14 tokens + mockup (human gate) ───────┘
              │                                                                           │
   A11 impact ──► [CP2]                                                                   ▼
              │                                                              A16 deterministic map ──► [CP3]
              ▼                                                                           │
 Python track:                                                            JS track (after CP3):
  A17 reference and integrity errors                                       A20 selection, detail, navigation
  A18 warnings and info                                                    A21 view switcher
  A19 CLI hardening, coverage ──► [CP4]                                    A22 view entries
                                                                           A23 decisions timeline
                                                                           A24 history
                                                                           A25 proposal preview
                                                                           A26 walkthroughs
                                                                           A27 progress filter
                                                                           A28 scale + design ──► [CP5: design review]
                                                                                          │
 A29 agents-md ─► A30 SKILL.md ─► A31 references ─► A32 worked examples ─► A33 packaging + isolation ──► [CP6]
                                                                                          │
                                                       A34 eval scenarios ──► A35 Cursor runs (human) ──► A36 release
```

## Task list

### Phase 0: Repository reorganisation
- [ ] P0: Commit and merge the approved spec, intent and this plan
- [ ] R1: Move docs and tasks
- [ ] R2: Move examples
- [ ] R3: Move tests, introduce `ontotest.py`
- [ ] R4: Rewrite `CLAUDE.md` for several skills
- [ ] R5: Rename the ontology page to "explorer", version 1.0.1

**Checkpoint 0:** R1–R4 leave `skills/curating-the-ontology/` unchanged and collect 490 tests with the same results. R5 passes separately. Phase 0 is reviewed and merged before A1 starts.

### Phase 1: Foundation
- [ ] A1: Walking skeleton (skill dir, CLI shell, `Finding`, test helpers)
- [ ] A2: Schemas, core vocabulary, core views, loader and `validate` (E001–E003)
- [ ] A3: `init`
- [ ] A4: Apply engine and replay for components, connections and vocabulary
- [ ] A5: Apply engine for view entries and view status
- [ ] A6: `propose` and `accept` (E006–E008, atomic writes, why refusal)
- [ ] A7: `withdraw`, `component`, `entry`, `show`

**Checkpoint 1:** `init → propose → accept → validate → show` round trip works in a temp git repo, and every authorship guard is tested.

### Phase 2: Risk first (code comparison, examples, design gate)
- [ ] A8: Ownership, Python imports, state derivation (W103–W106, W111, I202)
- [ ] A9: dbt reference reader and hybrid projects
- [ ] A10: Git layer, W107, W110
- [ ] A11: `impact`

**Checkpoint 2:** success criterion 4 passes on Python, dbt and hybrid temp projects, without dbt installed.

- [ ] A12: Analysis example
- [ ] A13: Hybrid pipeline example
- [ ] A14: Design tokens and static mockup. **Human gate.**
- [ ] A15: Vendored D3, build pipeline, data contract, W108
- [ ] A16: Deterministic map render

**Checkpoint 3:** the pipeline example's map renders from `file://` as the approved mockup shows. Review it together.

### Phase 3: Validator completion (Python track)
- [ ] A17: Reference and integrity errors (E004, E005, E009–E013)
- [ ] A18: Warnings and info (W101, W102, W109, W112–W114, I201, I203–I205)
- [ ] A19: CLI hardening, golden JSON, finding-coverage test

**Checkpoint 4:** every finding code has a fixture, the baseline is clean, and success criteria 1–4 pass.

### Phase 4: Explorer features (JS track)
- [ ] A20: Selection, component detail, navigation, deep links, keyboard
- [ ] A21: View switcher across all nine views
- [ ] A22: View entries panels
- [ ] A23: Decisions timeline
- [ ] A24: History stepping
- [ ] A25: Proposal preview
- [ ] A26: Walkthroughs
- [ ] A27: Progress counts and filter
- [ ] A28: Scale and design checks

**Checkpoint 5:** manual design review in both themes, at 1280×720 and on a large monitor, and with colour-blind simulation. Success criterion 5 passes.

### Phase 5: Skill packaging
- [ ] A29: `init --agents-md` and `--gitattributes`
- [ ] A30: `SKILL.md` body
- [ ] A31: References: schema, vocabulary, views
- [ ] A32: References: concepts, proposals, worked examples
- [ ] A33: Packaging and isolation tests, `CLAUDE.md` section

**Checkpoint 6:** full automated suite for both skills is green from a clean clone. Success criteria 6, 7 and 7a pass.

### Phase 6: Acceptance
- [ ] A34: Eval scenarios (a)–(h) and setup script
- [ ] A35: Cursor runs of (a)–(h), run by you
- [ ] A36: Release at version 1.0.0

**Done:** success criteria 1–8 met. The skill directory is ready to copy into the agentic-toolkit repo.

## Parallelisation

- Nothing in Phase 0 can run in parallel, because each move changes paths the next depends on.
- After CP1, three tracks touch separate files: code comparison (A8–A11), examples and mockup (A12–A14), and build (A15–A16).
- The mockup gate blocks only the JS track. Python work (A17–A19) continues during review.
- A20–A27 all edit the same app scripts, so they are best done in sequence, though they have few logical dependencies.
- References (A31, A32) can be drafted after CP1 and finalised after CP4.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Phase 0 silently changes ontology behaviour | High | Record per-test results before R1 and compare after each move. `git diff` on the skill directory must be empty for R1–R4. R5 is kept separate. |
| Replay diverges from the current target, so history is wrong | High | Decisions 3 and 4, built in Phase 1. A property-style test replays each fixture and both examples. |
| dbt text parsing produces false findings (comments, Jinja, packages, custom paths) | High | A9 is test-led across each listed case. Dynamic Jinja is ignored and documented as a limit. |
| The human-why rule is bypassed because a script can't tell who wrote it | High | Stated openly in the spec. `SKILL.md` hard rule, W102, and evals (a) and (d). |
| Partial multi-file accept corrupts the target | High | Decision 5, with an injected-failure test. |
| W107 is noisy or slow on long histories | Medium | Decision 10 compares parsed fields, and only walks commits touching those folders. |
| Nine views look like nine diagrams, or clutter the map | Medium | The mockup gate must show two views on one map. Decision 11 fixes positions. |
| The analysis case feels over-built | Medium | SC6 caps it at five components and two decisions. Eval (f) tests agent behaviour. |
| Windows paths and CRLF | Medium | POSIX paths inside `codemap`, parsed-content hash, CRLF test copy. |
| `SKILL.md` exceeds its size limit with two checkpoints and nine views | Medium | View detail lives in `references/` and `core-views.yaml`. The limit is tested. |
| The D3 copy drifts from the manifest | Low | Same checksum test as the sibling, on this skill's own copy. |

## Human touchpoints

- **P0:** approve this plan, then the merge of spec and plan.
- **Checkpoint 0:** approve the Phase 0 merge.
- **A14:** approve the mockup. This blocks explorer work.
- **Checkpoint 3:** look at the first rendered map.
- **Checkpoint 5:** manual design review.
- **A12, A13:** the examples need an accepted `why` for each decision. These are the human's words, so you write them (see Open questions).
- **A35:** run the Cursor scenarios.

## Working conventions

- **Branches:** `phase-0-repo-reorg`, then `arch-phase-1-foundation` and so on, each off `main`. Parallel tracks get their own branch.
- **Commits:** one per task, naming the task id, for example `refactor(repo): R1 move docs and tasks` or `feat(arch): A4 add apply engine`.
- **Merges:** into `main` with `--no-ff`, only after the checkpoint passes and you approve. `main` stays green. Nothing is pushed.
- **Plan location:** the ontology plan's open items (T27 and final acceptance) stay as they are, and R1 moves them to `tasks/ontology/`.

## Open questions

All resolved 2026-11-10.

1. ~~**Same-day replay order.**~~ **Resolved:** within one date, replay takes the lowest id that applies cleanly (Decision 3). Added to the spec.
2. ~~**A finding for a target that doesn't match replay.**~~ **Resolved:** add `W114`, in A18. Added to the spec.
3. ~~**Whys in the examples.**~~ **Resolved:** you write each example `why` when A12 and A13 reach them. Fixtures under `tests/` use obviously synthetic text.
4. ~~**Spec wording.**~~ **Resolved:** the Project Structure comment now says "unchanged by the moves".
