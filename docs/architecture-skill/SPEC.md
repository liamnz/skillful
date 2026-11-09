# Spec: `designing-the-architecture` skill

*Status: APPROVED 2026-11-10, amended 2026-11-10 during planning (same-day replay order, W114, one Project Structure comment). Source intent: [intent.md](intent.md). Sibling skill: [ontology spec](../ontology-skill/SPEC.md), whose conventions apply here unless this spec says otherwise. That link and other paths in this spec describe the repo after the reorganisation in phase 0.*

## Objective

Build an AI agent skill that keeps a human and an agent aligned on how a data solution is designed to meet its spec. The skill maintains a **target architecture** in the project repo: the design the team is building toward. Learning can change the target, but only through a deliberate, recorded decision.

Its purpose is to protect the human's mental model as more design and implementation move to agents. It guards against the failure this came from: many small, individually reasonable changes adding up to a design nobody chose and nobody can explain.

**One project, one target.** Each repo holds one solution, whether that is a data request, an analysis, a pipeline, a warehouse, a report or a dashboard. An analysis gets an architecture too, because it solves an information or decision problem with code. Depth scales with the work; the process does not change.

**Division of labour**

| Human | Agent | Scripts |
|---|---|---|
| Co-designs the shape of the solution | Drafts components, connections, view entries, options and trade-offs | Create and validate records against a fixed schema |
| Decides every change to the target | Tests whether the design is up to the spec | Apply accepted decisions to the target |
| Writes the *why* of each accepted decision in their own words | Critiques the human's why against the proposal and the spec | Compare the target with the code |
| | Owns detail inside components, and reports build status | Build the self-contained explorer |

**Hard rule: no target change without a human's why.** An agent may draft everything about a decision except its `why`. A decision is accepted only when a human has given that sentence or two, and the agent has transcribed it verbatim. This is the sibling of the ontology skill's rule that humans write the definitions. Approving a proposal asks little of the human, and writing the reason forces them to understand it.

**User stories**

1. An analyst has a spec for a churn analysis. The agent drafts a target of five components and two key decisions: how the cohort is defined, and why survival analysis was chosen over a simple rate. It walks through "a stakeholder challenges this number" against the design. The analyst changes one component, then says why they accept the design. The agent records those words and the map appears in the explorer. Deployment is marked not needed, with the reason that this is a one-off analysis.
2. An engineer plans a new feature on a pipeline. The agent reports: *"This fits the target: it lands in `orders-staging` and `orders-mart`."* Or: *"This doesn't fit: it needs a new store. Here is a proposal, with the option I rejected."* The target changes first, then the work is planned.
3. Before merging a branch, the agent runs `impact` and reports: *"One import crosses a boundary we didn't agree, and I learned the API can't serve history, which affects the target."* The human chooses to fix the code or to change the target through a decision.
4. A new team member opens `docs/architecture/index.html`. They see the map with what is built and what isn't, click a component to see its job and the decisions behind it, switch to the Runtime view to see what triggers each step on the same map, follow a walkthrough along the path it takes, and step back through how the target came to be.
5. A team lead drops the skill into a repo. One command scaffolds `docs/architecture/`, and nothing in the project's Python environment changes.

**Success (from intent):** With the agent switched off, a team member can sketch the system from memory, predict where a change lands, and spot when an agent's plan breaks the design, and the target has a visible record of why each change was made. This is qualitative. The testable criteria below cover only whether the tool works.

## Assumptions

1. **Same packaging as the ontology skill:** Agent Skills format, harness-neutral, Cursor as the primary harness, copied into each project via the agentic-toolkit repo.
2. **Same technical base:** Python ≥ 3.11 scripts with PEP 723 metadata run by `uv run --script`; runtime dependencies limited to `pyyaml` and `jsonschema`; committed offline HTML with a vendored D3 subset.
3. **Fully independent skills.** This skill shares no code or files with `curating-the-ontology` and does not require it. Duplication is the accepted cost of each skill being self-contained.
4. **A spec exists upstream.** The skill reads the project's spec and never writes or replaces it. Its depth varies by project.
5. **Python and dbt data teams.** A project may be Python, dbt, or a hybrid of both, and one component may own code of either kind. Code checks understand Python imports and dbt `ref()` and `source()` calls. Notebooks, non-dbt SQL and other files take part in path ownership only.
6. **Floor for use.** The skill applies when a wrong approach could produce a wrong answer that someone acts on. A single obvious query is below the floor.

## Concepts drawn from architecture practice

The human needs no formal training, so the skill teaches these in `references/` and in plain language in chat.

| Practice | Use here |
|---|---|
| **Architecture views** (ISO 42010, Kruchten's 4+1) | A solution is described through several views, each answering one question. The skill has a fixed set, and a project uses the ones it needs. |
| **C4 model** (showing systems at a level people can hold in mind) | One map of about 3–15 components, optionally grouped. No multi-level diagram hierarchy. |
| **Architecture Decision Records** | One record per decision. Accepted records are never rewritten, only superseded. |
| **Reflexion models** (comparing intended and actual structure) | Each component is on target, off target or absent, matching the reflexion terms convergence, divergence and absence. |
| **Quality-attribute scenarios** | Walkthroughs: concrete situations from the spec traced through the design. |

**Terminology.** *Component* is the everyday architecture term and means any main piece of the solution with a clear responsibility and connections, including external sources drawn on the map. It is broader than in the C4 model, where "component" is one specific level inside a container. `references/` explains the difference. A *view* always means an architecture view. The generated HTML page is called the *explorer*.

## Architecture views

A view answers one question about the solution. Every view has the same shape, defined once in `assets/schemas/core-views.yaml`: the question it answers, when it's needed, what it records, how it appears on the map, and the questions the agent asks to fill it in.

| View | Question it answers | Needed | Recorded in | On the map |
|---|---|---|---|---|
| **Context** | What's inside the solution, what's outside it, and who uses it? | Always | `views/context.yaml` | Marks the solution boundary and outside people and systems |
| **Components** | What are the main pieces and what is each responsible for? | Always | `components/` | Default map |
| **Data flow** | How does data move and change? | Always | `feeds` connections | Emphasises the `feeds` paths |
| **Decisions** | Why is it this shape? | Always | `decisions/` | Highlights the components a decision shaped |
| **Data** | What are the key datasets, their grain, keys and contracts? | Usually | `views/data.yaml` | Annotates components with their datasets and grain |
| **Runtime** | What triggers it, in what order, and what happens on failure? | When it runs more than once | `views/runtime.yaml` | Annotates components with triggers and run order |
| **Deployment** | Where does it run, and in which environments? | When it's deployed | `views/deployment.yaml` | Groups components by where they run |
| **Qualities** | How good must it be, and does the design achieve that? | Usually | `views/qualities.yaml`, `walkthroughs/` | Marks affected components; walkthroughs trace a path |
| **Cross-cutting** | What applies everywhere? | When relevant | `views/cross-cutting.yaml` | Highlights the components a concern touches |

- **Components are the backbone.** Other views attach entries to components, so a project has one model and not nine documents. In the explorer, switching view recolours and annotates the same map, so spatial memory carries across.
- **Every optional view has a recorded status.** It is `in_use`, `not_needed` with a reason, or `undecided`. A recorded reason shows the question was considered and lets the agent raise it again if the work grows, for example when an analysis becomes a scheduled report.
- **The set is fixed in v1.** Projects cannot define their own views.
- **Data is not the ontology.** The Data view covers datasets as built. Business meaning belongs in a domain ontology, and this skill doesn't require one.

## Target-project layout (what the skill creates)

```
docs/architecture/
  architecture.yaml          # manifest
  components/orders-staging.yaml  # one file per component; filename == id
  decisions/split-staging-from-marts.yaml  # one file per decision; filename == id
  views/runtime.yaml         # one file per stored view, created when first used
  walkthroughs/late-source-data.yaml       # belongs to the Qualities view
  index.html                 # generated, committed explorer
```

Decision ids are kebab-case slugs, not sequence numbers, so two branches can't collide on the same number. History is ordered by `accepted_on`, then id, with `initial-target` always first. Within one date, replay repeatedly takes the lowest id whose changes apply cleanly, so a decision never comes before one it depends on.

### Core vocabulary

The core ships with the skill, is the same in every project, and cannot be redefined. It is deliberately general so it fits an analysis as well as a pipeline.

| Term | Type | Meaning | Pipeline example | Analysis example |
|---|---|---|---|---|
| `source` | kind | Where data or input enters, from outside the solution's control | Orders API | Billing export |
| `step` | kind | Work that turns inputs into something new | Staging model | Cohort build, survival model |
| `store` | kind | Where results are kept for later use | Orders mart | Analysis dataset |
| `check` | kind | Establishes whether something can be trusted | Data tests | Reconciliation to finance |
| `output` | kind | What the audience receives | Dashboard | Findings memo |
| `service` | kind | Running software that others call | Scoring API | (rarely used) |
| `feeds` | connection | Data or control moves from source to target | | |
| `calls` | connection | Source uses the target's code or interface | | |
| `validates` | connection | Source checks the target | | |

There is no catch-all `related_to`: a connection that can't be named isn't yet understood. Projects may add kinds and connection types through a decision (`add_vocabulary`), and the added term needs a definition.

### Manifest (`architecture.yaml`)

```yaml
schema_version: 1
name: Churn analysis
description: Why customers leave, and which segments to act on.
specs: [docs/spec.md]            # upstream spec(s); paths must exist
code_roots: [src, models]        # optional; code here must belong to a component. Empty = W103 is off
groups: []                       # optional display groups: [{id, name}]
extensions: {kinds: {}, connection_types: {}}
views:                           # optional views only; `init` sets each to undecided
  data: {status: in_use}
  runtime: {status: in_use}
  deployment: {status: not_needed, reason: "One-off analysis run from a laptop."}
  qualities: {status: in_use}
  cross-cutting: {status: undecided}
settings:
  max_components: 15
  min_why_words: 8
  stale_proposal_days: 14
```

### Component record (`components/<id>.yaml`)

```yaml
id: cohort-build                 # kebab-case; must equal filename stem; stable
name: Cohort build
kind: step
status: agreed                   # agreed | retired
responsibility: >                # one or two sentences: what this component is for
  Decides which customers are in the study and fixes each one's start date.
group: null
connections:
  - {type: feeds, target: survival-model, decided_by: [initial-target]}
decided_by: [initial-target]     # accepted decisions that shaped this component
# Agent-maintained; changing these does not need a decision:
build: partial                   # planned | partial | built
owns: ["src/cohort/**"]          # paths or globs of the code belonging to this component
notes: ""
```

The fields above the agent-maintained comment make up the **target**. They change only when an accepted decision is applied. `owns`, `build` and `notes` describe progress and placement, so the agent keeps them current.

### Decision record (`decisions/<id>.yaml`)

```yaml
id: separate-cohort-step
title: Build the cohort as its own step
status: accepted                 # proposed | accepted | superseded | withdrawn
raised_at: planning              # initial | planning | merge
context: >                       # AGENT-DRAFTED
  The spec needs results by signup channel and by plan...
spec_refs: ["docs/spec.md#segments"]
options:                         # AGENT-DRAFTED; includes the rejected alternatives
  - {name: Separate step, tradeoffs: "One place to challenge who is in the study; one more component."}
  - {name: Inside the model, tradeoffs: "Less code; the population is hidden in modelling code."}
chosen: Separate step
why: >                           # HUMAN-WORDED. Required when accepted.
  The cohort is what people will argue about, so I want one place to point at.
consequences: ["Model changes can't silently change who is studied."]
changes:                         # applied to the target when accepted
  - {op: add_component, component: {id: cohort-build, name: Cohort build, kind: step, responsibility: "..."}}
  - {op: add_connection, from: cohort-build, type: feeds, to: survival-model}
accepted_on: 2026-11-09          # set by `accept`
supersedes: null
superseded_by: null
```

Operations in `changes`: `add_component`, `update_component`, `retire_component`, `add_connection`, `remove_connection`, `add_vocabulary`, `set_view_status`, `add_entry`, `update_entry`, `remove_entry`.

- **The first target is a decision too.** `initial-target` holds every starting component. There is one path into the target, and a small analysis needs little more than this one record.
- **A proposal doesn't change the target.** Its `changes` stay in the decision until `accept` applies them atomically, so the explorer can preview a proposal and history can be replayed.
- **Superseding, not rewriting.** After acceptance only `status` and `superseded_by` may change.

### View record (`views/<view-id>.yaml`)

```yaml
view: runtime
entries:
  - id: nightly-refresh          # kebab-case; unique within the view
    title: Nightly refresh
    statement: >                 # TARGET: changes only through a decision
      Rebuilds after the billing export lands, and stops rather than publishing partial results.
    components: [cohort-build, survival-model]
    decided_by: [initial-target]
    # Agent-maintained; changing these does not need a decision:
    facts: {trigger: "Billing export lands", schedule: "02:00 UTC", on_failure: "Alert data team"}
```

| View | Allowed `facts` keys |
|---|---|
| Context | `actor_type` (`person` or `system`), `role` |
| Data | `dataset`, `grain`, `keys`, `contract` |
| Runtime | `trigger`, `schedule`, `order`, `on_failure`, `how_to_reproduce` |
| Deployment | `environment`, `platform` |
| Qualities | `attribute`, `measure` |
| Cross-cutting | `concern` |

**What needs a decision.** The agent applies one test: *would changing this surprise someone relying on the design?* If so, it belongs in `statement` and changes through a decision and a why, for example moving from nightly to streaming, or stopping publication on failure. If not, it belongs in `facts`, and the agent keeps it current, for example a schedule moving by an hour.

### Walkthrough (`walkthroughs/<id>.yaml`, part of Qualities)

```yaml
id: challenged-number
name: A stakeholder challenges the headline number
situation: Finance questions the churn rate in the memo.
path: [findings-memo, survival-model, cohort-build, billing-export]
outcome: Every step back to source can be inspected; the cohort is the first thing to check.
open_concerns: []
```

Agents may draft these. They are how "is this design up to the job?" gets a concrete answer, and they let the explorer teach a route through the map. A walkthrough is evidence about the design and not part of the target, so it needs no decision.

## Commands

Run from the target repo root. `$SKILL` is the directory containing `SKILL.md`.

```
uv run --script $SKILL/scripts/arch.py init [--name "..."] [--spec <path>]... [--agents-md | --no-agents-md] [--gitattributes | --no-gitattributes]
uv run --script $SKILL/scripts/arch.py propose <id> --from <yaml-file>       # create a status=proposed decision
uv run --script $SKILL/scripts/arch.py accept <id> --why "..." | --why-file <path> [--date YYYY-MM-DD]   # apply changes atomically
uv run --script $SKILL/scripts/arch.py withdraw <id> --reason "..."
uv run --script $SKILL/scripts/arch.py component <id> [--build planned|partial|built] [--owns <glob>]... [--notes "..."]   # agent-maintained fields only
uv run --script $SKILL/scripts/arch.py entry <view-id> <entry-id> --fact key=value...   # agent-maintained facts only
uv run --script $SKILL/scripts/arch.py show [--view <view-id>] [--json]      # the current target, compactly, for use in planning
uv run --script $SKILL/scripts/arch.py validate [--json] [--strict]
uv run --script $SKILL/scripts/arch.py impact [--base <git-ref>] [--json]    # components touched, unowned changes, boundary crossings, open proposals
uv run --script $SKILL/scripts/arch.py build [--check]
```

Global option: `--root <path>` (default `docs/architecture`). Script conventions match the ontology skill: never interactive, `--help` everywhere, results on stdout and diagnostics on stderr, exit codes 0–4 with the same meanings, `--dry-run` on every write command, and `--limit` on long lists.

`accept` refuses (exit 3) if the why is empty, shorter than `min_why_words`, or the decision can't be applied cleanly. A script can't tell who wrote the words, so the human-authorship rule is held by `SKILL.md`, by W102, and by the record in git.

## Comparing the target with the code

Every agreed component has exactly one state, derived by the tool and applied in this order:

| Order | State | Rule | Meaning |
|---|---|---|---|
| 1 | **Off target** | Has code and a W105 finding | The code has departed from the design, and someone must choose: fix the code or change the target |
| 2 | **Absent** | No files match `owns` | The design is ahead of the code. This is normally expected progress, not a fault |
| 3 | **On target** | Has code and no departure was detected | Nothing the tool can see contradicts the design |

- **State and `build` are separate.** `build` is what the agent declares about progress; state is what the comparison finds. A half-built component with no departures is on target, and its `partial` outline shows it isn't finished.
- **Absent is neutral.** It carries no warning of its own. A component that claims `partial` or `built` while absent also gets W104, because its declared status is wrong.
- **Project-level departures.** Code that no component owns (W103) and retired components that still own files (W111) have no agreed component to attach to, so they are reported as off target for the project.
- **On target is not verified.** It means only that no departure was detected. The tool can't confirm that a component does its job, and the explorer must not imply that it has. The agent's merge review may report further departures as judgement, and those do not change the derived state.

**What the tool checks:** code that no component owns (only within `code_roots`), components claiming to be built with no code, and Python imports or dbt references between components with no declared connection. A dependency between two components is allowed if a connection of any type exists between them in either direction, because `feeds` may be implemented either way round.

**How dependencies are read.** Nothing is run or compiled, and neither dbt nor a warehouse connection is needed.
- *Python:* imports are read with `ast`.
- *dbt:* each `dbt_project.yml` in the repo gives its model, seed and snapshot paths. `ref()` and `source()` calls are read from the text of SQL models with comments removed, and `dbt.ref()` and `dbt.source()` from Python models with `ast`. A `ref()` resolves to the file of that name. A `source()` resolves to the YAML file that declares it. The dependency then belongs to whichever component owns that file.
- `target/manifest.json` is not used, because it is usually git-ignored and may be stale. References to dbt packages are ignored.

**Views other than Components and Data flow** are checked for valid references only. The tool does not compare Runtime or Deployment entries with a real orchestrator or environment, and it does not compare Data entries with a warehouse.

**What it can't check, stated plainly:** whether a component really does its job, references built dynamically with Jinja, whether notebooks or non-dbt SQL respect the boundaries, links that cross between Python and dbt (such as Python reading a mart by table name), or whether a branch honoured the intent of the design. Those are the agent's judgement at merge, and the agent presents them as judgement, not as tool results.

## Validator checks

| Code | Sev | Check |
|---|---|---|
| E001 | error | YAML fails to parse |
| E002 | error | Record violates the JSON Schema |
| E003 | error | `id` ≠ filename stem, or duplicate id |
| E004 | error | Connection, view entry, walkthrough or `supersedes` refers to something that doesn't exist |
| E005 | error | Kind or connection type is neither core nor a declared extension |
| E006 | error | An agreed component, connection or view entry has no accepted decision in `decided_by` |
| E007 | error | Accepted decision has an empty `why` |
| E008 | error | Proposed decision's `changes` can't be applied to the current target |
| E009 | error | Cycle or broken two-way link in `supersedes` / `superseded_by` |
| E010 | error | An extension reuses a core id |
| E011 | error | A path in `specs` does not exist |
| E012 | error | An optional view is `not_needed` with no reason |
| E013 | error | A view marked `not_needed` or `undecided` has entries or walkthroughs |
| W101 | warn | Responsibility is too short to say what the component is for |
| W102 | warn | `why` repeats text from the agent-drafted fields rather than being in someone's own words |
| W103 | warn | Code under `code_roots` is owned by no component |
| W104 | warn | Component says `partial` or `built`, but `owns` matches no files |
| W105 | warn | Python import or dbt `ref()` / `source()` between two components with no declared connection |
| W106 | warn | A path is owned by more than one component |
| W107 | warn | A component's target fields or a view entry's `statement` changed in git without a decision changing in the same commit |
| W108 | warn | `index.html` is stale relative to the records |
| W109 | warn | More than `max_components` agreed components: no longer at whiteboard level |
| W110 | warn | Decision still `proposed` after `stale_proposal_days` |
| W111 | warn | A retired component still owns files |
| W112 | warn | An optional view is still `undecided` after `initial-target` was accepted |
| W113 | warn | A view is `in_use` but has no entries or walkthroughs |
| W114 | warn | The current target differs from the result of replaying the accepted decisions |
| I201 | info | Component has no connections |
| I202 | info | Component says `planned`, but its owned files exist |
| I203 | info | Vocabulary extension is unused |
| I204 | info | Accepted decision records no rejected alternative |
| I205 | info | A Data, Runtime, Deployment or Qualities entry attaches to no component |

W107 and W110 skip gracefully outside git, with an info notice. Findings are sorted deterministically.

## Explorer (`index.html`)

**Design principle: built for learning.** The explorer is how someone gets a grip on the solution without reading long documents. It inherits the cross-cutting rules of the ontology skill's HTML view: self-contained, CSP `default-src 'none'`, works from `file://`, byte-for-byte reproducible, light and dark themes, desktop only at 1280×720 or larger, deep links, keyboard access, and tokens as the only home of raw style values.

- **View switcher.** One control lists all nine views, each with its question. Switching recolours and annotates the same map without moving any component. Views marked `not_needed` appear muted with their reason, and the current view is carried in deep links.
- **Map (landing screen).** Components as labelled boxes in a deterministic left-to-right layered layout following `feeds`, using a layered force so cycles and `calls` edges still place cleanly. Groups are drawn as quiet enclosures.
  - *Kind:* glyph colour and shape.
  - *Build status:* outline: solid `built`, half-dashed `partial`, dashed `planned`.
  - *Off target:* a finding badge using a symbol, not only a colour. Absent components show no state badge.
- **Component detail.** Responsibility, connections in sentence form, owned paths, build status, findings, its entries from each view in use, and the decisions that shaped the component, each showing its human `why` first.
- **View entries.** The panel for a stored view lists its entries. Agreed statements are shown separately from agent-maintained facts, and selecting an entry highlights its components.
- **Decisions.** A timeline, newest first. Each shows the why prominently, with options, trade-offs and consequences beneath. Agent-drafted text is labelled as such.
- **History.** Step through accepted decisions and see the map as it stood after each one. Snapshots are computed by replaying `changes`.
- **Proposal preview.** An open proposal can be overlaid on the map, showing what would be added, changed or retired.
- **Walkthroughs.** Choosing one highlights its path and steps through it component by component.
- **Progress.** A compact count of on target, off target and absent components, plus any project-level departures, which also acts as a filter.

The build embeds findings from the records and working tree only. Git-based findings are left out so that output stays reproducible. The freshness hash covers the records, so the agent rebuilds at each checkpoint to refresh code-based findings.

**Mockup gate.** As with the ontology skill, a static mockup in `examples/architecture/design/mockup.html` is reviewed and approved before the explorer is built. It must show the map, at least two views on that map, a component detail, a decision, a history step and a proposal preview in both themes.

The visual design follows the ontology spec's principles (information over decoration, neutral chrome, one encoding per dimension, quiet structure and loud focus), with its own token file inside this skill.

## Agent workflow (`SKILL.md` behaviour)

1. **Establish.** With no architecture yet, read the spec and draft the smallest target that meets it, sized to the work. Cover the four views that are always needed, then go through each optional view using its questions, and agree whether it's in use or not needed and why. Present the target in plain language with the key decisions and, if Qualities is in use, at least one walkthrough. Co-design it with the human, then ask for their why and record `initial-target`.
2. **Plan (first checkpoint).** Before planning a feature or enhancement, read the target across the views in use, ask whether a view marked `not_needed` is now needed, and say which it is:
   - **Fits:** name the components it lands in and any view entries it affects, and carry on.
   - **Doesn't fit:** propose a target change before planning the work.
   - **Unclear:** bring the question to the human.
3. **Propose.** A proposal gives what changes, why the spec needs it, at least one rejected option with its trade-offs, and a before-and-after in plain language. Teach any architecture idea it relies on, in a sentence.
4. **Ask for the why.** Ask the human why they would choose this, in their own words. Don't offer wording for them to confirm. Check their answer against the proposal and spec, and point out any mismatch or misunderstanding. Run `accept` with their words verbatim, apart from typo fixes they approve.
5. **While building.** Carry on within components without interrupting. If the work shows the target needs to change, note it for the merge checkpoint. Raise it immediately only if the remaining planned work no longer makes sense without an answer.
6. **Merge (second checkpoint).** Before merging, run `impact` and `validate`, read the diff, and report in a short message: what was built, what departs from the target, and what was learned. For each departure the human chooses to fix the code or change the target through a decision. Update `build`, `owns` and view `facts`, then run `build`.
7. **Explain.** When asked how something works or where a change would land, answer from the target, and point at the relevant view in the explorer.
8. **Scale.** Keep small work small: a few components, one or two decisions, only the views the work needs, and a light merge check. Don't add ceremony the work doesn't need.
9. **Apply the surprise test.** Before changing anything in a view, ask whether the change would surprise someone relying on the design. If it would, propose a decision. If it wouldn't, update `facts`. When unsure, ask the human.

`references/` holds, each with a "read when" trigger: the schema guide, the vocabulary with analysis and pipeline examples, the views and the questions for each, architecture concepts in plain language, how to write good proposals and trade-offs, and worked examples at both ends of the size range.

## Packaging and distribution

Same lifecycle and rules as the ontology skill: self-contained directory, conforming `SKILL.md` with `metadata.version`, body under 500 lines and about 3,800 words, "Hard rules" first, references one level deep, no harness-specific terms, and `compatibility: Requires git and uv`.

Draft description: *"Keeps a human and agent aligned on a project's target solution architecture in docs/architecture/: co-designs how the solution meets its spec, checks plans against the design, records deliberate design decisions, compares the design with the code, and builds a visual map. Use when planning a feature, starting a data request, analysis, pipeline or dashboard from a spec, preparing to merge a branch, or when the user mentions architecture, design decisions, or how the solution fits together."*

`init --agents-md`, with consent, adds a marked section to `AGENTS.md` that makes the two checkpoints always-on. Without it, they depend on the skill happening to be loaded.

## Project Structure (this repo)

Both skills are first-class, and every dev-only area has one folder per skill:

```
skills/curating-the-ontology/       # unchanged by the moves
skills/designing-the-architecture/
  SKILL.md
  scripts/arch.py               # PEP 723 entry point
  scripts/archkit/              # cli, io, schema, checks, apply, codemap, gitinfo, impact, build
  references/                   # schema, vocabulary, views, concepts, proposals, examples
  assets/schemas/               # JSON Schemas, core-vocabulary.yaml, core-views.yaml
  assets/templates/  assets/html/  assets/vendor/
tests/ontology/                 # test_onto_*.py; own conftest, fixtures and golden files (moved from tests/)
tests/architecture/             # test_arch_*.py; own conftest, fixtures and golden files
examples/ontology/                  # sample-project/, design/, evals.md, evals/
examples/architecture/              # pipeline/ (hybrid Python and dbt), analysis/, design/, evals.md, evals/
docs/ontology-skill/                # SPEC.md, intent.md
docs/architecture-skill/            # SPEC.md, intent.md
tasks/ontology/                     # plan.md, todo.md
tasks/architecture/                 # plan.md, todo.md
CLAUDE.md  pytest.ini  ruff.toml    # shared repo-level files
```

## Phase 0: repository reorganisation

The first set of tasks makes the repo accommodate both skills as equals, before any architecture skill code is written. Each task is one commit using `git mv` so history is kept, and each leaves the full test suite passing.

| Task | Moves | Also updates |
|---|---|---|
| **R1: docs and tasks** | `docs/SPEC.md` → `docs/ontology-skill/SPEC.md`; `docs/intent/ontology-skill.md` → `docs/ontology-skill/intent.md`; `tasks/plan.md` and `todo.md` → `tasks/ontology/` | The spec path read by the finding-coverage test; the links and Project Structure section in the ontology spec |
| **R2: examples** | `examples/sample-project/`, `design/`, `evals.md` and `evals/` → `examples/ontology/` | `SAMPLE` paths in tests and `setup_eval.py`; references in the ontology spec, `evals.md`, the sample README and the mockup caption |
| **R3: tests** | All of `tests/` → `tests/ontology/`, including `conftest.py`, `gen_large_fixture.py`, `fixtures/` and `golden/`; each `test_<name>.py` → `test_onto_<name>.py` | The repo root in `conftest.py`; shared helpers moved to `ontotest.py`; `tests/fixtures/large/` in `.gitignore`; usage comments; the Project Structure and Testing Strategy sections of the ontology spec |
| **R4: repo guidance** | None | `CLAUDE.md` rewritten so it describes the repo as a home for several skills: shared conventions first, then a section for each skill, with commands for running one skill's tests or all of them |

- **Each skill's tests stand alone.** There is no shared `tests/conftest.py`, so neither skill depends on the other's setup. Module prefixes (`test_onto_`, `test_arch_`) keep names unique. The ontology tests currently use `from conftest import ...` in 25 modules, which would collide once two suites each have a `conftest.py`. R3 therefore moves those helpers into a uniquely named `tests/ontology/ontotest.py`, leaving only pytest fixtures in `conftest.py`, and the architecture tests use `tests/architecture/archtest.py`. Running both suites in one `pytest` command is part of the acceptance check.
- **Records stay put.** Files in `tasks/ontology/` move, but their contents are left as a historical record, so old paths in them are expected. The ontology spec keeps its approved content and changes only where paths are named.
- **The moves (R1–R4) must not change behaviour.**
  - `git diff` shows no changes under `skills/curating-the-ontology/`.
  - The full suite, including browser tests, collects the same number of tests with the same results before and after.
  - Golden files don't change when regenerated, and `examples/ontology/sample-project/docs/ontology/index.html` remains current.
  - `ruff check` and `ruff format --check` pass.
- **R5: rename the ontology page to "explorer".** This follows R1–R4 and starts only after their checks pass, so the wording change can't blur the check that the moves left the skill unchanged. With two skills in one repo, "view" must mean only an architecture view.
  - *Changes:* wording that means the page, in `SKILL.md`, references, script help and messages, the ontology spec's "HTML view" section, `CLAUDE.md` and test comments. `SKILL.md` says "the ontology explorer" on first mention.
  - *Stays the same:* "Fit to view" on the toolbar, the graph, list and hierarchy screens, internal code names such as `graph-view.js`, the `build` command, `index.html`, schemas and finding codes.
  - *Also:* set `metadata.version` to `1.0.1`, regenerate the sample project's page and any golden output whose text changed, and record the terminology change as a dated amendment in the ontology spec.
  - *Check:* the full suite passes, including browser tests, and the only behaviour differences are the changed wording and version.
- **Checkpoint.** Phase 0 is reviewed and merged into `main` on its own, before phase 1 begins.

## Code Style

As the ontology skill: typed Python, `ruff`, small pure functions, I/O and git at the edges, checks return findings and never print. `apply.py` is pure, so `accept`, E008, the proposal preview and history replay all use the same logic.

```python
def apply_changes(target: Target, changes: list[Change], decision_id: str) -> Target:
    """Return a new target with the changes applied, or raise ChangeConflict."""
    result = target
    for change in changes:
        result = APPLIERS[change.op](result, change, decision_id)
    return result
```

## Testing Strategy

Commands follow the sibling skill's (`uv run --with pytest --with pyyaml --with jsonschema pytest tests/architecture -q`, with `pytest-playwright` for browser tests).

- **Finding coverage:** one fixture per code over a baseline with no findings; the code table here is kept in sync with the `CODES` registry.
- **Apply logic:** each operation including view entries and status, atomicity on failure, and replay reproducing the current target.
- **Views:** `core-views.yaml` defines all nine views in the standard shape; per-view `facts` keys are enforced; each optional view can be in use or not needed.
- **Authorship guards:** `accept` refuses an empty or short why; `component` cannot touch target fields; `entry` can change only `facts`; accepted records cannot be rewritten through any command.
- **Code comparison:** in temporary Python, dbt and hybrid projects: ownership, globs, relative imports, `ref()` and `source()` resolution, custom model paths, comments, dbt package references, and SQL and Python dbt models. State derivation follows the precedence order, including a `partial` component with no departures (on target) and a `built` component with no code (absent, with W104).
- **Git and CLI:** W107, W110 and `impact` in temporary repos, the `init → propose → accept → validate → build` round trip, exit codes, golden JSON and the no-git fallback.
- **Packaging and isolation:** the same checks as the ontology skill, including copying to arbitrary locations.
- **HTML:** reproducible builds, no network, contrast and colour-blind token checks, and Playwright tests for map, view switching (no component moves), history, preview and walkthroughs.
- **Agent behaviour (eval scenarios in Cursor):**
  - (a) the agent never records a why the human didn't give;
  - (b) a plan that doesn't fit produces a proposal before work is planned;
  - (c) a plan that fits does not trigger a proposal or ceremony;
  - (d) a why that contradicts the proposal gets challenged;
  - (e) a merge check surfaces a seeded boundary crossing;
  - (f) a small analysis stays small, and unused views are marked not needed with a reason;
  - (g) a surprising runtime change produces a proposal, while a minor schedule change updates `facts` only;
  - (h) when an analysis becomes a scheduled report, the agent raises the Runtime view at planning.

## Boundaries

- **Always:** change the target only through accepted decisions; keep agent-drafted text labelled and separate from the human why; validate after edits and rebuild after changes; keep the explorer offline and output deterministic; keep the skill self-contained and harness-neutral.
- **Ask first:** adding a runtime dependency; changing the schema or `schema_version`; changing the core vocabulary or the set of core views; changing finding codes; upgrading vendored D3.
- **Never:**
  - Have an agent write, suggest or alter a `why`, or run `accept` without the human's own words.
  - Edit target fields by hand, or rewrite an accepted decision.
  - Write or replace the project's spec.
  - Modify a project's `pyproject.toml`, lockfile or virtual environment.
  - Edit `AGENTS.md` outside the marked section or without consent.
  - Automatically block work, or wire anything into CI or pre-commit.
  - Depend on `curating-the-ontology`.
  - Use harness-specific features in the skill.

## Out of scope for v1

Writing specs; design inside components; deep or multi-language code analysis; repos holding many unrelated analyses; multi-level diagrams; project-defined views; comparing Runtime, Deployment or Data entries with real infrastructure; CI or pre-commit wiring; migrations between schema versions.

## Success Criteria

1. `init` in an empty git repo creates the layout, and `validate` exits 0 with no warnings.
2. `accept` applies a decision's changes atomically, refuses a missing or too-short why, and leaves the target unchanged on failure.
3. Every finding code has a fixture, and the baseline triggers none. A target change without an accepted decision is always reported (E006, or W107 or W114 for later edits).
4. `impact` lists touched components, unowned changes, undeclared Python imports and dbt references between components, and open proposals, including uncommitted changes. It works on Python, dbt and hybrid projects without dbt installed.
5. The explorer shows the map with build status, all nine views on that same map without moving components, component and decision details, history, proposal preview and walkthroughs. It is deterministic, offline and reproducible, and it passes the browser tests. The mockup was approved first.
6. The same skill serves both example projects: the analysis example has at most five components and two decisions and marks unused views as not needed, and the pipeline example exercises the full workflow and every view.
7. Isolation and packaging tests pass, including copying to any location and independence from the ontology skill.
7a. Phase 0 is complete: the repo has the layout under "Project Structure"; after R1–R4 the ontology skill is unchanged and the ontology tests give the same count and results as before the moves; and after R5 the ontology skill is at `1.0.1`, calls its page the explorer, and its full suite passes.
8. The eval scenarios behave as described under "Testing Strategy", in Cursor.

## Open Questions

1. ~~**Walkthroughs in v1?**~~ **Resolved:** keep them, as part of the Qualities view. They make "up to the job?" concrete and teach a route through the map.
2. ~~**"Test yourself" mode?**~~ **Resolved:** left out of v1.
3. ~~**Skill name.**~~ **Resolved:** `designing-the-architecture`. It is plain, matches the team's own language of co-design, and keeps the term "architecture" so it says what level the skill works at. It is also the directory name and the `name` frontmatter field.
