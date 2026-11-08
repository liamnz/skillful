# Spec: `curating-the-ontology` skill

*Status: APPROVED 2026-11-08. Source intent: [docs/intent/ontology-skill.md](intent/ontology-skill.md).*

## Objective

Build an AI agent skill that helps a data team keep an explicit, human-owned **ontology** of each project's domain. The ontology lives in the project repo, and its purpose is to protect the team's mental model as more coding moves to agents.

In Gruber's terms, an ontology is "an explicit specification of a conceptualization". Here, the *conceptualization* is what the team understands about the domain. The ontology is the *explicit specification*: versioned, reviewable, and shared.

**Division of labour**

| Humans | Agent | Scripts |
|---|---|---|
| Write concept definitions in their own words | Notices new or changed concepts while working, and proposes them briefly at the end of a task | Scaffold, create and validate records against a fixed schema |
| Promote concepts from `proposed` to `defined` | Critiques human definitions against the code and the rest of the ontology | Detect drift between the ontology and the code (git-based) |
| Revise muddy concepts over time | Runs health checks and explains the findings | Build the self-contained HTML view |
| | Uses the ontology as its own working vocabulary | |

**User stories**

1. An analyst finishes an agentic task that introduced `churned_account` in a new model. The agent says: *"This task introduced 1 concept that isn't in the ontology: `churned-account`. Want to define it?"* With the analyst's agreement, the agent creates a `proposed` stub. The analyst writes the definition themselves, either in the YAML or by dictating it in chat.
2. An analyst asks for an "ontology health check". The agent runs the validator and summarises the findings, grouped by Gruber criterion. It offers fixes, but it never rewrites a definition on its own.
3. A new team member opens `docs/ontology/index.html` and lands on a graph of the domain. They click **Active customer**, its neighbourhood lights up, and they follow `has → Order` and `measured_by → Retention rate` to see how the concepts connect. They turn on the *Mud* overlay to see which parts of the domain are still only proposed or have drifted from the code. Along the way they build a spatial mental map of the domain without having to read a list of terms.
4. A team lead adopts the skill in a new repo. One command scaffolds `docs/ontology/`, and nothing in the project's own Python environment changes.

**Success (from intent):** Qualitative. The team likes the ontology and relies on it to keep their understanding of each codebase. The testable criteria below cover only whether the tool works. They are not a stand-in for that outcome.

## Assumptions

1. **Skill format, harness-agnostic.** The skill follows the [Agent Skills specification](https://agentskills.io/specification) and its best practices: a `SKILL.md` with spec-conformant frontmatter, plus `scripts/`, `references/` and `assets/`. It relies on no harness-specific features. The team's primary harness is **Cursor**, but nothing in the skill may assume Cursor, Claude Code or any other harness (see "Packaging and distribution").
2. **This repo develops the skill.** The finished skill directory is published into the team's **agentic-toolkit** repo alongside other skills. From there it is **copied into each project**. It is never installed at user level. Target projects are separate repos.
3. **Scripts.** The scripts are Python ≥ 3.11 single-entry CLIs with PEP 723 inline metadata, run via `uv run`. Runtime dependencies are limited to `pyyaml` and `jsonschema`.
4. **HTML.** The HTML view uses vanilla HTML, CSS and JS, inlined at build time. There are no CDNs or network requests, and it works from `file://`. The graph is rendered as SVG using a small, pinned, vendored subset of **D3**, which is inlined like everything else. **Desktop only:** people use the view on a laptop or desktop screen with a mouse or trackpad, so there are no phone or tablet layouts and no touch-specific interactions. The minimum supported viewport is 1280×720.
5. **Ontology location.** Each target repo has one ontology, at `docs/ontology/`.
6. **Committed view.** The generated `index.html` is committed, so a fresh clone has the ontology ready to browse without running anything. The validator warns when it is stale.

## Tech Stack

- **Python** ≥ 3.11 for the scripts, run with `uv run` (PEP 723). Dependencies: `pyyaml>=6`, `jsonschema>=4`.
- **JSON Schema** (draft 2020-12) for the concept and manifest schemas. It is the single source of truth for record structure.
- **git**, invoked through `subprocess`, for drift and staleness checks.
- **HTML view:** no application framework and no external assets. The only third-party code is a vendored D3 subset.
  - **D3 (vendored, pinned, ISC licence):**
    - `d3-selection` for data-joined SVG rendering;
    - `d3-force` for the layout simulation;
    - `d3-zoom` and `d3-drag` for pan, zoom (mouse wheel and trackpad) and drag-to-pin;
    - `d3-shape` for its seven built-in symbols, used as kind shapes;
    - plus their internal dependencies (e.g. `d3-quadtree`, `d3-dispatch`, `d3-timer`, `d3-interpolate`, `d3-transition`, `d3-ease`, `d3-color`, `d3-path`).
    - Modules are the official standalone UMD builds, concatenated in dependency order at build time. No npm or bundler is needed, in this repo or in target projects.
  - **D3 is used for physics and gestures only.** Everything else is written for this skill: labels, semantic zoom, focus and fading, overlays, panels, keyboard navigation, accessibility and URL state. D3 imposes no visual style.
  - **Force layout:**
    - `d3-force`, with initial positions seeded from concept ids and a seeded `simulation.randomSource()`;
    - a fixed number of ticks run synchronously, then a single render. There's no animated settling, so the result is deterministic and suits reduced motion.
  - **Hierarchy layout:** a *layered force*, i.e. `d3-force` plus a vertical force that pulls each concept to its depth level in the acyclic relations. This handles multiple parents (`is_a` forms a DAG, not a tree), which `d3-hierarchy` cannot. No `d3-dag` or other non-D3 library.
  - **Code organisation:** graph-query logic (neighbourhood, filtering, depth levels) consists of pure functions with no D3 dependency, kept separate from rendering, so it can be tested.
- **Dev only:**
  - `pytest` and `ruff`, invoked with `uv run --with` and never added to target projects.
  - `playwright` (via `uv run --with playwright`) for HTML smoke and interaction tests in this repo only.

## Target-project layout (what the skill creates)

```
docs/ontology/
  ontology.yaml          # manifest: name, description, schema_version, vocabularies, settings
  concepts/
    active-customer.yaml # one file per concept; filename == id
    churned-account.yaml
  index.html             # generated, self-contained human view (committed)
```

### Vocabulary: a fixed core plus disciplined extensions

Kinds and relation types are the vocabulary used to *describe* concepts, so they need the same care as the concepts themselves. Otherwise the synonym problem simply moves up a level: `related_to`, `associated_with` and `linked_to` all in one ontology, each meaning whatever the reader assumes.

**Core vocabulary.** It ships with the skill, is identical in every project, and cannot be removed or redefined. The tooling relies on what these terms mean: hierarchy layout, cycle checks, kind constraints and default visual encodings. The kinds divide cleanly: a thing with identity is an `entity`, a happening is an `event`, a property of one instance is an `attribute`, and an aggregate across many instances is a `metric`. Their definitions live in the skill (`assets/schemas/core-vocabulary.yaml`, explained in `references/vocabulary.md`) and are embedded in the HTML legend.

| Core term | Type | Meaning |
|---|---|---|
| `entity` | kind | A thing the domain keeps track of over time, with an identity of its own (e.g. Customer, Order). |
| `event` | kind | Something that happens at a point in time and is recorded (e.g. Order placed, Subscription cancelled). |
| `attribute` | kind | A property describing a single entity or event, with no identity of its own (e.g. Customer region, Order amount). |
| `metric` | kind | A quantity computed by aggregating over many instances of entities or events, to assess something (e.g. Retention rate, Average order value). A numeric property of a single instance is an `attribute`, not a metric. |
| `is_a` | relation | Source is a subtype of target: every instance of the source is an instance of the target. Acyclic and transitive. Inverse label: `has_subtype`. |
| `part_of` | relation | Source is a component of target and makes no sense without it. Acyclic. Inverse label: `has_part`. |
| `attribute_of` | relation | Source attribute describes instances of the target. `from: [attribute]`, `to: [entity, event]`. Inverse label: `has_attribute`. |
| `related_to` | relation | Symmetric catch-all for a connection nobody has named precisely yet. Allowed, but the validator flags each use as an invitation to name the relationship (I204). |

**Extensions.** Each project declares its own kinds and relation types in `ontology.yaml` to fit its domain. An extension is governed like a concept:
- It has a `status` (`proposed | defined | deprecated`).
- It needs a **human-written definition** before it becomes `defined`.
- The agent may propose one (with a `proposal.rationale`) but never adds or defines one itself.

Relation-type extensions also declare an `inverse` label and may declare `acyclic` and allowed source and target kinds (`from` and `to`), which the validator then checks. An extension may not reuse a core id.

### Manifest (`ontology.yaml`)

```yaml
schema_version: 1
name: Acme Analytics
description: Domain concepts for the Acme analytics warehouse.

# Core vocabulary is built in and cannot be redefined here:
#   kinds:          entity, event, attribute, metric
#   relation types: is_a, part_of, attribute_of, related_to

extensions:
  kinds:
    rule:
      status: defined
      definition: >                 # HUMAN-AUTHORED, same rule as concept definitions
        A business policy or constraint the domain must obey, such as
        "a refund cannot exceed the original order amount".
  relation_types:
    measures:
      status: defined
      definition: >
        The source metric is computed from instances of the target and
        summarises some aspect of them.
      inverse: measured_by
      acyclic: false
      from: [metric]                # optional: allowed source kinds (core or extension)
      to: [entity, event]           # optional: allowed target kinds
    derived_from:
      status: proposed
      definition: ""
      inverse: source_of
      proposal:                     # AGENT-AUTHORED; present only while status=proposed
        rationale: "Several metrics are computed from other metrics; neither is_a nor measures fits."

settings:
  stale_proposal_days: 30
  min_definition_words: 8
  drift_context_lines: 3           # W106: changed lines within this distance of a symbol mention count as "near" it
```

`init` writes a manifest with **no active extensions**. A set of commented-out *starter extensions* (`rule`, `has`, `derived_from`, `measures`) comes with suggested definitions. Teams uncomment them and rewrite the definitions in their own words, so every extension a project uses is a deliberate choice.

### Concept record (`concepts/<id>.yaml`)

```yaml
id: active-customer                 # kebab-case; must equal filename stem; stable
name: Active customer               # the ONE canonical term; humans and agents use only this
kind: entity                        # a core kind or a kind extension
status: defined                     # proposed | defined | deprecated
definition: >                       # HUMAN-AUTHORED. Empty allowed only when status=proposed.
  A customer who has made at least one paid order in the trailing
  90 days, regardless of subscription state.
discouraged_terms:                  # variants to RECOGNISE and REDIRECT, never to use; unique across the ontology
  - {term: active user, note: "Product team's usage"}
examples: ["A customer whose last paid order was 12 days ago"]
non_examples: ["A customer on a free trial with no paid orders"]
rules:                              # invariants in plain language
  - "Every active customer is a customer."
relations:                          # type: a core relation type or a relation-type extension
  - {type: is_a, target: customer}
  - {type: related_to, target: order}  # I204 will ask: can this relationship be named more precisely?
  - {type: has, target: subscription, cardinality: "1:N"}  # optional; read source:target, i.e. one active customer has many subscriptions
implemented_in:                     # where the concept lives in code; drives drift checks
  - path: models/marts/dim_customer.sql
    symbol: is_active               # optional; text searched for in the file; narrows drift checks to nearby changes
    reviewed_at: 3f9c2e1            # commit at which a human last confirmed the definition matches this code; set by `review`
open_questions: ["Should refunded orders count?"]
proposal:                           # AGENT-AUTHORED; present only while status=proposed
  rationale: "Introduced as churned_account in models/marts/fct_churn.sql"
  suggested_definition: "..."       # optional; shown in HTML clearly labelled as an agent suggestion
replaced_by: null                   # id; required when status=deprecated and the concept was renamed or merged
```

**Authorship rule:** `definition` and the `proposed → defined` transition belong to humans, for concepts and vocabulary extensions alike. The agent may write a human-supplied definition into the file only when the human dictates the text in chat. In that case the agent transcribes it verbatim, apart from typo fixes the human approves. Git history is the authorship record. No `author` fields.

**One term per concept:** `name` is the single canonical term. `discouraged_terms` exists only so that variants already in circulation (stakeholder jargon, legacy names, terms an agent invented) can be recognised and redirected to the canonical concept. They are not equal synonyms, and nobody, human or agent, should use them in new code, docs or conversation.
- A variant that doesn't map cleanly onto the concept (e.g. "MAU" is actually narrower than "Active customer") is not a discouraged term. It points to a separate concept that should be proposed.
- Code identifiers (column and model names) are never discouraged terms. They belong in `implemented_in.symbol`, which keeps naming in the code separate from the domain vocabulary.

**Cardinality (optional):** a relation entry may carry `cardinality`, read from source to target: `1:1`, `1:N`, `N:1` or `N:M`. For example, `{type: has, target: order, cardinality: "1:N"}` on Customer means one customer has many orders.
- **Why it's there.** Misunderstood cardinality causes the classic analytics bug, a join that fans out and double-counts a metric. "Can an order belong to more than one customer?" is exactly the kind of domain fact people hold vaguely, so writing it down where people can see it is worth the small cost.
- **Never required.** In line with *minimal ontological commitment*, it's left out when it's meaningless or unknown. A missing cardinality is never flagged, so nobody is pushed into guessing.
- **Where it's allowed:** on `part_of`, `related_to` and relation-type extensions. It's an error on `is_a` and `attribute_of`, where it means nothing (E013). Because `related_to` is symmetric, it may only be `1:1` or `N:M` there (E013).
- **Optionality stays out.** Whether a link may be absent ("zero or one", "at least one") goes in `rules` or `open_questions`, which keeps the field to four values.
- **Domain, not table grain.** Cardinality records what's true of the domain, not the grain of a particular table. When the two differ (e.g. the domain says one customer per order, but `fct_orders` allows several), that's worth an `open_question`, not a silent choice. `references/gruber-criteria.md` covers this under *minimal encoding bias*.
- **Authorship.** Cardinality is a domain claim, like a definition. The agent may *suggest* one in a proposal (for example from unique keys or join patterns it saw in the code) and say where the evidence came from, but it writes the value only after a human confirms it.

## Commands

All commands run from the target repo root. `$SKILL` is the skill's directory *inside the project*, i.e. wherever the project's harness expects skills, such as Cursor's project skills folder. `SKILL.md` tells the agent to resolve `$SKILL` as "the directory containing this `SKILL.md`", so the instructions work at any location. The scripts locate their own `assets/` via `__file__`, never via cwd or a hard-coded path.

Scripts are run as `uv run --script ...`, which forces the PEP 723 inline-metadata environment so uv never resolves or syncs the host project. The isolation test verifies this.

```
uv run --script $SKILL/scripts/onto.py init [--name "Acme Analytics"] [--agents-md | --no-agents-md] [--gitattributes | --no-gitattributes]   # scaffold docs/ontology/; optionally add the AGENTS.md pointer and the .gitattributes line
uv run --script $SKILL/scripts/onto.py new <id> --name "<Name>" --kind <kind> \
       [--rationale "..."] [--suggested-definition "..."] \
       [--implemented-in path[:symbol]]...                          # create a status=proposed stub
uv run --script $SKILL/scripts/onto.py vocab new kind <id> --rationale "..."  # propose a kind extension (status=proposed)
uv run --script $SKILL/scripts/onto.py vocab new relation <id> --inverse <label> \
       [--acyclic] [--from <kind>...] [--to <kind>...] --rationale "..."   # propose a relation-type extension
uv run --script $SKILL/scripts/onto.py vocab list [--json]                    # core + extensions, with status and usage counts
uv run --script $SKILL/scripts/onto.py review <id> [--path <path>]           # record "definition still matches the code" at HEAD (sets reviewed_at)
uv run --script $SKILL/scripts/onto.py validate [--json] [--strict]          # health check; exit 1 on errors (warnings too with --strict)
uv run --script $SKILL/scripts/onto.py impact [--base <git-ref>] [--json]    # concepts touched by changes; changed files mapped to no concept
uv run --script $SKILL/scripts/onto.py build [--check]                       # write docs/ontology/index.html (--check: exit 1 if stale)
```

Global option: `--root <path>` (default `docs/ontology`).

**Script conventions** (from the Agent Skills guidance on scripts):
- **Never interactive.** Agents run in non-interactive shells, where a prompt would hang forever. Choices that need the user's consent are asked *by the agent in chat* and passed to the script as flags. For example, `init` without `--agents-md` or `--no-agents-md` changes nothing in `AGENTS.md`; it prints a one-line hint to stderr.
- **`--help`** on every command and subcommand, with usage examples.
- **Output streams.** Machine-readable results go to stdout (`--json` where noted). Diagnostics and progress go to stderr.
- **Actionable errors** that say what went wrong, what was expected and what to try. For example: `Error: --kind must be one of: entity, event, attribute, metric, rule. Received: "measure". Run "onto.py vocab list" to see all kinds.`
- **Documented exit codes:**
  - `0` success;
  - `1` validation errors (or warnings with `--strict`) / stale build with `--check`;
  - `2` usage error;
  - `3` refused, e.g. an id already exists, or a core vocabulary id was given;
  - `4` environment problem, e.g. not run from a git repo root when one is required.
- **Safe writes.** Every command that writes files (`init`, `new`, `vocab new`, `review`, `build`) accepts `--dry-run`, which prints what would change and writes nothing. Writes are idempotent where that makes sense (`init`, `build`). Nothing is overwritten without an explicit refusal path.
- **Bounded output.** Findings and impact lists accept `--limit` so very large ontologies can't flood the agent's context.

Development commands in this repo:

```
uv run --with pytest --with pyyaml --with jsonschema pytest tests/ -q
uv run --with ruff ruff check . && uv run --with ruff ruff format --check .
skills-ref validate skills/curating-the-ontology     # Agent Skills reference validator (pinned version, run via uvx; exact invocation set during implementation)
```

## Validator checks

Each finding has a stable code, a severity, a concept id (if any), a message, and the Gruber criterion it relates to. `--json` emits a list of findings for the agent to consume.

| Code | Sev | Criterion | Check |
|---|---|---|---|
| E001 | error | — | YAML fails to parse |
| E002 | error | — | Record violates the JSON Schema |
| E003 | error | — | `id` ≠ filename stem, or duplicate id |
| E004 | error | Coherence | Relation target does not exist |
| E005 | error | Coherence | Relation type or kind is neither core nor a declared extension |
| E006 | error | Coherence | Cycle in an `acyclic` relation type (e.g. `is_a`) |
| E007 | error | Coherence | A term (name or discouraged term) belongs to two concepts, i.e. one word with two meanings; the concepts need distinct names |
| E008 | error | — | `status: defined` with an empty definition |
| E009 | error | Drift | `implemented_in.path` does not exist |
| E010 | error | Coherence | An extension reuses a core vocabulary id, or two extensions share an id |
| E011 | error | Clarity | Vocabulary extension is `defined` with an empty definition |
| E012 | error | Coherence | Relation-type extension's `from`/`to` names an unknown kind |
| E013 | error | Coherence | `cardinality` not allowed for this relation: set on `is_a` or `attribute_of`, or set to `1:N`/`N:1` on the symmetric `related_to` |
| E014 | error | Coherence | The same relationship is stated more than once with conflicting cardinality (e.g. a symmetric `related_to` recorded on both concepts as `1:1` and `N:M`) |
| W101 | warn | Clarity | Definition shorter than `min_definition_words` |
| W102 | warn | Clarity | Definition is circular (uses the concept's own name or one of its discouraged terms as its main term) |
| W103 | warn | Min. encoding bias | Definition mentions an `implemented_in` path or symbol, i.e. the concept is defined by its implementation |
| W104 | warn | Coherence | Relation targets a `deprecated` concept |
| W105 | warn | Drift | `implemented_in.symbol` not found in its file |
| W106 | warn | Drift | Relevant code changed since the concept was last reviewed (see "Drift detection (W106)") |
| W107 | warn | Staleness | Concept or vocabulary extension still `proposed` after `stale_proposal_days` (by git date) |
| W108 | warn | — | `index.html` is stale relative to the records |
| W109 | warn | Coherence | A definition, rule or example uses another concept's discouraged term instead of its canonical name |
| W110 | warn | Coherence | Relation breaks its type's `from`/`to` constraint (e.g. `measures` from an `entity`) |
| W111 | warn | Coherence | `is_a` links concepts of different kinds |
| W112 | warn | Coherence | Concept or relation uses a `deprecated` vocabulary extension |
| W113 | warn | Clarity | More than 8 kinds are in use, so the graph can no longer encode each kind distinctly |
| I201 | info | Min. commitment | Concept has no relations and no `implemented_in` (is it needed?) |
| I202 | info | Extendibility | Deprecated concept without `replaced_by` |
| I203 | info | Min. commitment | Vocabulary extension is declared but no concept or relation uses it |
| I204 | info | Clarity | `related_to` is used; can the relationship be named more precisely? |
| I205 | info | Drift | `reviewed_at` commit is not in history (e.g. after a rebase or squash); W106 falls back to the concept file's last commit |

The git-based checks (W106, W107) degrade gracefully. Outside a git repo, or for uncommitted files, they are skipped and an info notice explains why.

### Drift detection (W106)

W106 asks: *has code relevant to this concept changed since a human last confirmed the definition?* It is computed separately for each `implemented_in` entry.

1. **Baseline.** The baseline is `reviewed_at` if it is set and reachable in history. Otherwise it is the last commit that touched the concept file. If `reviewed_at` is set but unreachable, I205 is reported as well.
2. **Relevant change.**
   - *With a `symbol`:* the check runs `git diff <baseline>..HEAD` on the path, plus uncommitted changes. It fires only if a changed hunk has added or removed lines within `drift_context_lines` of a line that mentions the symbol, in either the old or the new version. Unrelated edits elsewhere in a shared file (e.g. a new column in a mart model) don't trigger it.
   - *Without a `symbol`:* any change to the file since the baseline counts.
3. **Clearing it.** The only way to clear W106 is a deliberate review: `onto.py review <id>` sets `reviewed_at` to HEAD for that concept's entries (or a single `--path`). Editing the concept file for some other reason doesn't count as a review once `reviewed_at` exists, so nobody has to make fake edits to silence it. A review is recorded in git like any other change.
4. **Proposed concepts are skipped.** They have no confirmed definition to drift from yet.

**Known limits, stated plainly.**
- W106 is a prompt to check, not a guarantee.
- It can't see logic that lives somewhere `implemented_in` doesn't list, such as an upstream model, a macro or a project variable that changes the meaning.
- Reformatting the lines around a symbol still triggers it.
- The agent's end-of-task review (`impact` plus reading the diff) is the main defence against drift. W106 is the backstop for drift that happened while nobody was looking.

## `impact` command

This command gives the agent a deterministic starting point for its end-of-task proposals:

- Changed files, from `git diff --name-only <base>...HEAD` plus uncommitted changes. The default base is the merge-base with the default branch.
- For each changed file, the concepts whose `implemented_in` references it ("review these definitions").
- Changed files referenced by no concept ("possible new concepts").

Deciding whether an unmapped file really introduces a domain concept is the agent's job, not the script's.

## HTML view (`index.html`)

**Design principle: visual first.** The HTML view is how the skill gets humans to *use* the ontology, so it is a core part of the design, not a report bolted on at the end. Reading lists of terms takes a lot of effort and discourages use. A well-designed, interactive picture of how concepts connect is cheaper to take in, easier to explore and easier to remember, and it gives people a mental map. **The interactive relationship graph is the primary view in v1.** The list and detail views support it.

### Overall layout

- **Graph canvas** takes most of the screen and is the landing view.
- **Concept detail pane** opens beside the graph when a concept is selected.
- **Toolbar** across the top with search, filters, overlays and layout controls.
- **List view** is a secondary tab: a sortable, filterable table of all concepts. It shares the same selection and filters as the graph.

### Graph view

- **Visual encoding.**
  - *Kind* is shown by colour **and** shape, so colour is never the only cue.
  - *Status* is shown as solid (`defined`), dashed or hollow (`proposed`, i.e. "needs a definition") or faded (`deprecated`).
  - Concepts with validator findings get a badge whose colour reflects severity.
  - Edges are directed (`related_to` is drawn undirected), styled by relation type and labelled on hover or focus. The label includes the cardinality when one is recorded (e.g. `has · 1:N`). There are no crow's-foot or other cardinality marks at rest, to keep the structure quiet. A legend of kinds and relation types is always visible, and hovering a legend entry shows its definition.
  - Core kinds have fixed encodings in every project, so the same kind looks the same everywhere. Kind extensions get colour/shape pairs from a fixed palette, assigned deterministically by sorted id so they don't change between builds. Beyond 8 kinds, the extra kinds share a neutral fallback encoding and W113 explains why.
- **Focus and neighbourhood (main way to cut clutter).** Selecting a concept centres it, opens its detail pane, and highlights its neighbourhood (concepts up to N hops away; default 1, adjustable 1–3) while fading the rest. People explore one neighbourhood at a time instead of the whole hairball.
- **Exploration.** Pan, zoom and fit-to-view. Drag a concept to pin it in place, and reset the layout. Clicking a related concept moves the focus there, and breadcrumbs let you step back.
- **Hover preview.** Hovering shows the concept's name, kind and the first sentence of its definition, without changing the selection.
- **Semantic zoom.** When zoomed out, only labels of high-degree or selected concepts are shown; zooming in reveals all labels. The graph stays readable at about 300 concepts.
- **Deterministic layout; stability as a best effort.**
  - **Guaranteed:** the same ontology always produces the same layout. Positions are seeded from concept ids and the layout runs a fixed number of iterations.
  - **Best effort:** across edits, id-seeding tends to keep familiar concepts roughly where they were, so a small addition usually only nudges its neighbours. This helps people's spatial memory of the domain survive rebuilds.
  - **Not guaranteed:** larger changes are allowed to reshape the picture. When the model genuinely evolves, the layout *should* reflect it. `build` does not carry positions over from previous builds.
- **Hierarchy option.** A toggle lays out `acyclic` relation types (core `is_a` and `part_of`, plus any extension marked `acyclic`) as a top-down hierarchy instead of a force layout.
- **Overlays** (toggleable):
  - *Health:* highlights concepts with findings, grouped by Gruber criterion.
  - *Mud:* highlights `proposed` concepts, concepts with open questions, and relations that use `related_to` or a `proposed` relation type.
  - *Drift:* highlights concepts with W105/W106 findings.
- **Filters** by kind, status and relation type apply to the graph and the list alike. Filtered-out concepts are hidden, and dangling edges are drawn as stubs so it's clear something is connected off-screen.

### Search

- Search matches names, discouraged terms and definition text, works from the keyboard (`/` to focus, arrow keys, Enter to select), and moves the graph's focus to the chosen concept.
- **Redirecting search.** Searching for a discouraged term finds the concept but shows it as a redirect (*"'active user' → use **Active customer**"*), not as an equal match.

### Concept detail pane

- Shows the definition, examples, non-examples, rules, open questions, and incoming and outgoing relations as clickable links (inverse labels from the manifest). Where a cardinality is recorded, the relation reads as a sentence: "Customer **has many** Orders" on Customer. On the target concept it uses the inverse label with the cardinality flipped, e.g. "Order **belongs to one** Customer" when the inverse label is `belongs_to`.
- Includes a small embedded neighbourhood mini-graph.
- `implemented_in` paths are shown as relative links, each with its last-reviewed commit and date, or "never reviewed".
- **Honest about mud.** `proposed` concepts are visibly marked as needing a definition. Agent suggestions are visually separate and labelled as such. The concept's validator findings are listed with their codes and criteria.

### Health panel

- Lists all findings grouped by criterion. Clicking a finding focuses the concept in the graph.

### Vocabulary panel

- Lists core and extension kinds and relation types, with definitions, status (core / defined / proposed / deprecated), `from`/`to` constraints and usage counts.
- Clicking an entry filters the graph to the concepts or relations that use it.

### Cross-cutting requirements

- **Self-contained.** A single file with the records embedded as JSON and all CSS, JS and vendored libraries inline. No network access, no external fonts, and it works from `file://`.
- **Navigation state in the URL.** Deep links via `#<concept-id>`, optionally with view state (e.g. `#active-customer?depth=2&overlay=health`), so people can share links to specific views.
- **Accessibility.**
  - The list and detail views give complete, non-visual access to everything in the graph.
  - In the graph, concepts are keyboard-reachable: Tab and arrow keys move between connected concepts, and Enter selects.
  - It respects `prefers-reduced-motion` (no animated settling; the layout is pre-computed).
  - Text and graph elements meet WCAG AA contrast in both themes.
- **Themes and sizes.** Light and dark themes follow `prefers-color-scheme`. It is designed for laptop and desktop screens (minimum viewport 1280×720) and scales up to large monitors. Phone and tablet layouts are out of scope.
- **Performance.** Fixture ontology with 300 concepts and 600 relations: first render in under 2 s on a typical laptop, and pan, zoom and selection stay smooth.
- **Freshness.** The build embeds a hash of the input records so `validate`/`build --check` can detect staleness.
- **Friendly to being committed.**
  - The output is **byte-for-byte reproducible**: no timestamps, stable key and record ordering, pinned templates. Two people building from the same records always produce an identical file.
  - `init` offers, asking first, to add `docs/ontology/index.html -diff linguist-generated=true` to `.gitattributes`. Diffs and PR reviews then show the YAML changes, not the regenerated HTML.
  - **Merge conflicts in `index.html` are resolved by rebuilding:** merge the YAML, run `build`, and commit the result. The agent workflow and `references/workflow.md` say so, and the agent does it automatically when it hits such a conflict.

## Visual design

**Goal:** minimal, coherent and highly legible. The view exists to convey the domain's structure and meaning, not to impress. These principles and tokens are binding for every part of the HTML view.

### Principles

1. **Information over decoration.** Every visual element either carries meaning or gets out of the way. No gradients, drop shadows, decorative icons, illustrations or animation for its own sake. In Tufte's terms, maximise the share of ink that carries data.
2. **Colour is reserved for meaning.** Interface chrome (toolbar, panels, tables, controls) uses only neutral greys. Colour appears only where it encodes something:
   - *kind* on graph nodes and in the legend;
   - *severity* on finding badges;
   - *focus/selection*.
   
   Because colour is scarce, it carries information when it does appear.
3. **One encoding per dimension, never overloaded.**

   | Dimension | Encoding | Not encoded by |
   |---|---|---|
   | Kind | colour **and** shape | — |
   | Status | outline style: solid (`defined`), dashed (`proposed`), reduced opacity (`deprecated`) | colour |
   | Severity | small badge using the semantic colour family | kind colours |
   | Relation type | edge stroke pattern (solid, dashed, dotted, …) plus arrowheads; label (with cardinality, if recorded) on hover/focus | colour |
   | Focus | full contrast plus the accent outline; everything else fades | — |

   Nobody should have to wonder whether "orange" means *metric* or *warning*. The kind palette and semantic palette are chosen so they don't clash.
4. **Quiet structure, loud focus.** At rest, edges are thin and low-contrast, and labels are muted. The selected concept and its neighbourhood get full contrast. The focus interaction does the visual work, rather than everything competing at once.
5. **Text is the main content.** Definitions are the human contribution and are set for comfortable reading: body size, generous line height (~1.5) and a measure of about 65 characters. They're never squeezed into cramped panel text.

### Design tokens

All styling flows from CSS custom properties defined once in `assets/html/tokens.css`, with a light and a dark value for each. Components never use raw colour, size or spacing values.

- **Neutrals:** a 7-step grey ramp mapped to roles: `--bg`, `--surface`, `--surface-raised`, `--border`, `--text-faint`, `--text-muted`, `--text`.
- **Kind palette:** 8 slots (`--kind-1` … `--kind-8`).
  - Colour-blind-safe as a set (distinguishable under protanopia, deuteranopia and tritanopia simulation).
  - Each meets WCAG AA non-text contrast (≥ 3:1) against `--bg` in both themes.
  - The four core kinds have **fixed slots and shapes**: `entity` → slot 1 + circle, `event` → slot 2 + diamond, `attribute` → slot 3 + square, `metric` → slot 4 + triangle. Slots 5–8 and the remaining `d3-shape` symbols are assigned to extension kinds by sorted id.
  - Kinds beyond 8 use a neutral fallback (see W113).
- **Semantic colours:** `--accent` (focus/selection; one hue only, and not confused with any kind colour), `--error`, `--warn`, `--info`.
- **Typography:**
  - `--font-ui`: system UI stack (`system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`). No web fonts, because the page must work offline.
  - `--font-mono` for ids, paths and symbols.
  - A 5-step type scale (`--text-xs` … `--text-xl`); base body size 15–16 px.
  - Tabular figures (`font-variant-numeric: tabular-nums`) for counts and dates.
  - At most two weights (regular and semibold).
- **Spacing and shape:** a 4 px base scale (`--space-1` … `--space-8`), one border width (1 px), two radii (`--radius-sm`, `--radius-md`). No elevation or shadows; panels are separated by borders and surface tone.
- **Motion:** `--duration-fast: 150ms` with an ease-out curve, used only for focus/fade transitions and panel open/close. Reduced to `0ms` under `prefers-reduced-motion`. The layout is never animated (see "Tech Stack").

### Graph style

- Nodes are small (a radius comparable to the label's cap height), so structure shows before detail.
- Labels sit beside nodes in `--text-muted`. They become `--text` when focused or in the neighbourhood. Each label has a `--bg`-coloured halo (stroke under the text) so it stays readable over edges.
- Edges are 1 px in `--border` at rest. Focused neighbourhood edges use `--text-muted` with visible arrowheads, and their relation label appears on hover or focus.
- Hover, selected and in-neighbourhood states are each visually distinct.
- The canvas has no background grid or other chart junk. Pan and zoom controls are small, neutral and out of the way.
- **Legibility check at scale:** with the 300-concept fixture zoomed to fit, the graph must read as a structure (clusters and hubs visible), not a hairball. Semantic zoom and focus are the means of getting there.

### Design mockup gate

Before the full view is implemented, a **static mockup** is produced and reviewed with the user. It uses the tokens above and the `examples/sample-project` data, and it shows:
- the graph view with one concept selected;
- the detail pane;
- the legend;
- a finding badge;
- light and dark themes.

Feedback is folded into the tokens and this section, and implementation proceeds only after explicit approval. The mockup lives in `examples/design/mockup.html` and is not part of the shipped skill.

## Agent workflow (`SKILL.md` behaviour)

1. **Consult.** When working in a repo that has `docs/ontology/`, read the relevant concepts and use their names and definitions as the working vocabulary. If the code being written or read contradicts a definition, say so instead of silently picking one side.
   - **Canonical terms only.** In code it writes, in docs and in chat, the agent uses only canonical `name`s.
   - **Redirect variants.** When the human, the code or a ticket uses a discouraged term, the agent states the mapping once (*"taking 'active user' to mean **Active customer**"*) and continues with the canonical term.
   - **Variants that don't fit.** If a term in use doesn't map cleanly onto any concept, the agent treats it as a candidate new concept, not a synonym.
2. **End-of-task proposals (primary trigger).** After a task that changed code:
   - Run `impact`.
   - Combine its output with what the agent knows from the diff.
   - Name at most 3 new or changed concepts in one short message, one line each with its rationale.
   - It may suggest a relation's cardinality with its evidence (e.g. "`fct_orders` has one `customer_id` per order, so Customer has Order `1:N`?"). It records it only after the human confirms.
   - With the human's agreement, create `proposed` stubs using `new`, never by hand-writing YAML.
   - Invite the human to write the definition in their own words.
   - If the human declines, drop it without nagging.
3. **Vocabulary.**
   - **Use what exists first.** Before proposing a new relation type or kind, the agent checks whether a core term or existing extension fits.
   - **Propose only when nothing fits.** If nothing fits, the agent proposes an extension with `vocab new` and a rationale explaining why the existing terms don't fit. It never adds or defines vocabulary itself.
   - **Challenge near-duplicates** (*"is `linked_to` different from `related_to`?"*).
   - **Turn `related_to` into a named relationship.** When it sees `related_to`, the agent asks the human what the relationship actually is.
4. **Critique.** When a human writes or edits a definition, check it against the code (`implemented_in`), the related concepts, and the Gruber criteria. Ask pointed questions, for example: "your definition says 90 days; `fct_retention.sql` uses 30. Which is right?"
   - **Reviews.** When a W106 finding or an end-of-task change leads to a discussion and the human confirms the definition still holds, the agent offers to record that with `review <id>`. It never runs `review` without the human's confirmation: a review is a human claim that the definition matches the code.
5. **Health check (on demand).** Run `validate --json`. Summarise the findings grouped by criterion, most important first. Offer concrete fixes. Structural fixes (relations, paths, discouraged terms) may be applied with consent. Definitions, for concepts and vocabulary alike, remain the human's to write.
6. **Rebuild.** After any change to the ontology, run `build`. If a merge or rebase conflicts in `index.html`, resolve the YAML first, then rebuild rather than hand-merging the HTML.
7. **Init.** If a user asks to start an ontology and none exists, run `init`. Ask whether to add the `AGENTS.md` pointer, and explain that without it, the end-of-task proposals depend on the harness happening to load the skill.

`references/` holds the material the agent loads on demand: the schema guide, the Gruber criteria with examples of good and bad definitions, and this workflow in more detail.

## Packaging and distribution

**Lifecycle:**
1. The skill is developed and tested here.
2. The `skills/curating-the-ontology/` directory is copied into the **agentic-toolkit** repo.
3. From the toolkit, that directory is copied into a project, at whichever location the project's harness reads skills from.
4. The project commits the copy.

There is no user-level install, no package registry, and no install script.

**Copy-safe skill directory:**
- `skills/curating-the-ontology/` is **self-contained**: no references to files outside it, and no dependency on this repo's tests, examples or tooling.
- Copying the folder is the entire install.
- Dev-only material (`tests/`, `examples/`) lives outside it and is never copied.

**Agent Skills conformance and harness-agnostic rules:**
- `SKILL.md` conforms to the Agent Skills specification and passes `skills-ref validate`. Its frontmatter is:
  ```yaml
  ---
  name: curating-the-ontology        # 1–64 chars, a–z/0–9/hyphens, no leading/trailing/double hyphens; equals the directory name
  description: >-                    # ≤ 1024 chars; says what it does AND when to use it, with trigger keywords
    Curates a human-owned domain ontology kept in docs/ontology/: proposes new or
    changed domain concepts at the end of coding tasks, critiques human-written
    definitions against the code, runs health checks for consistency and drift, and
    builds an interactive HTML graph of the concepts. Use when working in a repo that
    has docs/ontology/, when a task introduces or changes domain terms, data models,
    metrics or business rules, or when the user mentions the ontology, domain
    concepts, glossary, definitions, terminology or what a domain term means.
  compatibility: Requires git and uv (uv provides Python 3.11+ and script dependencies).
  metadata:
    version: "1.0.0"                 # string; semver; bumped on every toolkit release
  ---
  ```
  `license` is omitted until the toolkit picks a licence (the vendored D3 keeps its own ISC notice regardless). `allowed-tools` is not used: it is experimental and harness-specific.
- **Progressive disclosure.** The `SKILL.md` body stays under 500 lines and about 5,000 tokens. It contains the workflow, the hard rules (authorship, canonical terms, consent) and the gotchas. Everything else lives in `references/` and is loaded only when needed.
- **Reference rules.** Every reference is linked by a relative path from the skill root, one level deep, with an explicit "when to read" trigger. For example: *"Read `references/vocabulary.md` before proposing a new kind or relation type."* Reference files don't link onward to further references.
- No harness-specific features or vocabulary: no hooks, slash commands, subagents, harness environment variables, or tool names such as "Edit tool" or "Bash tool".
- Instructions are phrased as actions ("run …", "read …", "ask the user …") that any coding agent can carry out with a shell and file access.
- Every deterministic behaviour lives in the scripts, not in harness features, so the skill behaves the same wherever it runs.

**Always-on pointer (AGENTS.md).**
- *The problem:* the end-of-task proposal trigger only works if the agent has the skill in mind when a task ends, and harnesses load skills on demand based on the description.
- *The fix:* when the user agrees (the agent asks, then passes `--agents-md`), `init` adds a short, clearly delimited section to the project's `AGENTS.md`, creating the file if needed. `AGENTS.md` is the cross-harness convention for always-loaded project instructions.
- *Content:* that section says only that the repo has an ontology at `docs/ontology/`, that canonical terms must be used, and that the `curating-the-ontology` skill should be followed at the end of any task that changed code.
- *Idempotent:* the section sits between marker comments, so re-running `init` updates it in place rather than duplicating it.

**Versioning and updates:**
- The skill carries a version: `version` under `metadata` in the frontmatter, and `onto.py --version`.
- Updating a project means replacing its copy of the skill directory with the newer toolkit copy.
- Project data (`docs/ontology/`) lives outside the skill directory, so updating the skill never touches it.
- If a future schema change requires it, `validate` reports a `schema_version` mismatch and points to a migration command. Migrations themselves are out of scope for v1.

## Project Structure (this repo)

```
skills/curating-the-ontology/   # SELF-CONTAINED: this folder is what gets copied to the toolkit and into projects
  SKILL.md                      # spec-conformant frontmatter; workflow, hard rules, gotchas; < 500 lines
  scripts/
    onto.py                     # PEP 723 entry point; thin CLI over ontokit
    ontokit/                    # package: io.py, schema.py, checks.py, gitinfo.py, impact.py, build.py
  references/                   # loaded on demand; one level deep; each linked from SKILL.md with a "when to read" trigger
    schema.md                   # concept + manifest fields; read before creating or editing records by hand
    vocabulary.md               # core vocabulary meanings; when/how to extend; avoiding near-duplicates
    gruber-criteria.md          # the five criteria with good/bad definition examples, incl. cardinality vs table grain; read when critiquing definitions
    workflow.md                 # detailed proposal, review, health-check and conflict-resolution procedures
  assets/                       # static resources used by the scripts
    schemas/concept.schema.json
    schemas/manifest.schema.json
    schemas/core-vocabulary.yaml   # core kinds + relation types with definitions and fixed visual encodings
    templates/ontology.yaml        # manifest written by `init` (no active extensions; commented-out starter extensions)
    templates/agents-md-section.md # always-on pointer inserted into a project's AGENTS.md by `init --agents-md`
    html/index.html             # HTML shell; css/js inlined by build.py
    html/tokens.css             # design tokens (CSS custom properties, light + dark); the only place raw values live
    html/app.css                # component styles; uses tokens only
    html/app.js                 # app shell: state, URL routing, search, filters, list/detail/health/vocabulary views
    html/graph-model.js         # pure, no D3: neighbourhood queries, filtering, depth levels, seeded initial positions
    html/graph-view.js          # D3: force + layered-force layout, SVG rendering, zoom/drag, focus, overlays, keyboard nav
    vendor/                     # pinned D3 UMD builds (one file per module), inlined by build.py
    vendor/MANIFEST.json        # module, exact version, source URL, SHA-256, concatenation order
    vendor/LICENSE-d3.txt       # ISC licence text; its notice is also emitted as a comment in index.html
tests/
  fixtures/<case>/docs/ontology/...   # one fixture per check code + a valid baseline
  fixtures/large/             # generated 300-concept / 600-relation ontology for performance checks
  test_validate.py  test_new.py  test_vocab.py  test_impact.py  test_build.py  test_isolation.py
  test_packaging.py           # skill dir is self-contained, harness-neutral, and works after being copied anywhere
  test_html_ui.py             # Playwright: graph interactions, determinism, performance, a11y smoke
examples/sample-project/      # small dbt-style repo with a populated ontology, used for manual and eval runs
examples/design/mockup.html   # static design mockup reviewed at the design gate (not shipped)
docs/intent/ontology-skill.md
docs/SPEC.md
```

## Code Style

- Python with type hints, formatted and linted with `ruff`. Functions should be small and pure where possible. I/O and git access stay at the edges (`io.py`, `gitinfo.py`), and checks are pure functions over loaded records.
- Each check returns `Finding`s and never prints. Only the CLI formats output.
- Output is deterministic: findings are sorted by (severity, concept id, code) so diffs and tests are stable.

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6", "jsonschema>=4"]
# ///
from dataclasses import dataclass

@dataclass(frozen=True)
class Finding:
    code: str            # e.g. "W103"
    severity: str        # "error" | "warn" | "info"
    concept: str | None
    criterion: str | None
    message: str

def check_encoding_bias(concept: Concept) -> list[Finding]:
    refs = {i.path for i in concept.implemented_in} | {i.symbol for i in concept.implemented_in if i.symbol}
    hits = sorted(r for r in refs if r in concept.definition)
    if not hits:
        return []
    return [Finding("W103", "warn", concept.id, "minimal-encoding-bias",
                    f"Definition references implementation detail(s) {hits}; define the idea, not the code.")]
```

## Testing Strategy

- **Unit tests (pytest)** for each check against minimal fixtures: one fixture per finding code, plus a valid baseline that must produce zero errors and zero warnings.
- **CLI tests:** `init → new → validate → build` round trip in a temp dir. Exit codes. Golden `--json` output.
- **Git tests:** temp repos created in tests to exercise W106, W107, I205, `review` and `impact` (commit ordering, merge-base, uncommitted files, and the no-git fallback). For W106 specifically:
  - an unrelated edit elsewhere in a shared file does **not** fire;
  - an edit near the symbol does fire;
  - with no symbol, any edit to the file fires;
  - `review` clears the finding;
  - an unrelated edit to the concept file does not clear it once `reviewed_at` exists;
  - an unreachable `reviewed_at` falls back to the concept file's date and reports I205.
- **HTML static tests (pytest):** the output parses, contains the embedded data and the input hash, and contains no `http(s)://` references in `src`/`href`/`@import`. Two builds from the same records, in different directories and at different times, are byte-identical.
- **HTML interaction tests (Playwright, dev only)**, loading the page from `file://` with network access blocked:
  - The graph renders one node per visible concept and one edge per visible relation.
  - Selecting a concept highlights exactly its N-hop neighbourhood and opens the detail pane.
  - Filters and overlays change what is visible or highlighted as specified.
  - Deep links restore the selection, depth and overlay.
  - Searching a discouraged term shows the redirect and focuses the canonical concept.
  - Keyboard navigation moves between connected concepts.
  - An edge with a recorded cardinality shows it in its hover label, and the detail pane renders it as a sentence in both directions. Edges without one show no cardinality.
  - **Determinism:** two loads of the same build give identical node positions. (Movement when concepts are added is best effort and not tested against a threshold. It is only checked in the manual design review.)
  - **Performance:** the large fixture renders in under 2 s.
  - Zero console errors.
- **Design token checks (pytest):**
  - Parse `tokens.css` and compute WCAG contrast for every text/background token pair (≥ 4.5:1 for text, ≥ 3:1 for kind colours and UI boundaries) in both themes.
  - Check the kind palette is distinguishable under protanopia, deuteranopia and tritanopia simulation (minimum pairwise colour difference in a perceptual space, e.g. CIEDE2000, above a set threshold).
  - Lint `app.css` and the JS for raw colour, size or spacing literals outside `tokens.css`.
- **Manual design review:** in a browser, check against the five design principles: visual quality and legibility in both themes, at the minimum 1280×720 viewport and on a large monitor, with reduced motion and under colour-blind simulation, using the sample project and the large fixture. This includes the "structure, not a hairball" check at 300 concepts.
- **Isolation test:** running every command in a fixture project that has its own `pyproject.toml`, `uv.lock` and `.venv` leaves those byte-identical.
- **Packaging tests:**
  - Copy `skills/curating-the-ontology/` to arbitrary, differently nested locations in a temp project, and run every command from the project root.
  - Assert the skill directory references nothing outside itself.
  - `skills-ref validate` passes (frontmatter fields and constraints, name equals directory name).
  - Lint `SKILL.md`:
    - the body is under 500 lines;
    - every file reference is relative, resolves, and is one level deep;
    - no harness-specific terms from a denylist (e.g. hook, slash-command and subagent syntax, harness tool names, harness environment variables).
  - Script conventions:
    - every command supports `--help`;
    - no command reads stdin interactively (run with stdin closed, and none hangs);
    - every write command honours `--dry-run` by writing nothing;
    - each documented exit code is tested.
  - `init --agents-md` is idempotent: re-running it updates the marked section without duplicating it, and leaves the rest of `AGENTS.md` untouched.
  - **Vendor integrity:** every file in `assets/vendor/` is listed in `MANIFEST.json` and matches its SHA-256 checksum; nothing unlisted is present; the ISC notice appears in built `index.html`.
- **Skill behaviour (manual / eval scenarios)** in `examples/sample-project`, run in **Cursor** only. Harness-agnosticism is enforced by design rules and the packaging tests, not by running the scenarios in other harnesses:
  - (a) a task that introduces a concept triggers ≤ 3 proposals and creates a stub only after consent;
  - (b) the agent never sets `status: defined` or writes `definition` without dictated text;
  - (c) a health check groups findings by criterion;
  - (d) a definition that contradicts the code gets challenged;
  - (e) when the user uses a discouraged term, the agent states the mapping once and uses the canonical name from then on;
  - (f) when no relation type fits, the agent proposes an extension with a rationale rather than inventing one inline, and challenges a proposed near-duplicate of an existing type.

## Boundaries

- **Always:**
  - Create and modify records through the scripts or the schema.
  - Run `validate` after ontology edits and `build` after changes.
  - Keep findings deterministic.
  - Keep the HTML fully offline.
  - Keep agent suggestions labelled and separate from human definitions.
  - Keep `skills/curating-the-ontology/` self-contained and harness-neutral.
- **Ask first:**
  - Adding any runtime dependency beyond `pyyaml` and `jsonschema`.
  - Vendoring any third-party JS into the HTML view other than the pinned D3 modules, or upgrading D3's version (update `MANIFEST.json` checksums, then re-run the determinism and interaction tests).
  - Changing the concept schema or bumping `schema_version`.
  - Changing the core vocabulary in the skill (it affects every project's ontology and visual encoding).
  - Changing finding codes.
  - The agent creating stubs, or applying structural fixes, in a user's ontology.
- **Never:**
  - Modify a target project's `pyproject.toml`, lockfile or virtualenv.
  - Have the agent write or alter a `definition`, or set `status: defined`, on its own authority (concepts and vocabulary extensions).
  - Have the agent run `review` without the human confirming the definition still matches the code.
  - Redefine or override core vocabulary from within a project.
  - Use harness-specific features (hooks, slash commands, subagents, harness env vars or tool names) in the skill.
  - Edit a project's `AGENTS.md` outside the marked section, or without the user's consent.
  - Make proposals block or gate work.
  - Load assets from the network in the HTML.
  - Add decoration to the HTML view (shadows, gradients, decorative icons or imagery, gratuitous animation), use colour in chrome, or use raw style values outside `tokens.css`.
  - Wire anything into CI or pre-commit (out of scope for now).

## Success Criteria

1. `init` in an empty git repo creates the layout above, and `validate` exits 0 with no warnings.
2. `new` produces a schema-valid `proposed` record whose filename equals its id. It refuses to overwrite an existing id or to set any status other than `proposed`. `vocab new` likewise adds only `proposed` extensions, and refuses core ids and duplicates.
2a. `init` writes a manifest with no active extensions. Uncommenting the starter extensions yields a manifest that validates cleanly.
3. Every finding code in the table has a fixture that triggers it, and the valid baseline triggers none.
4. `validate` exits 1 on any error, and exits 0 when there are only warnings unless `--strict` is passed. `--json` output matches the golden files.
5. `impact` correctly lists concepts affected by changed files and unmapped changed files, including uncommitted changes.
5a. W106 fires only for changes near a concept's symbol (or anywhere in the file when there's no symbol) since its last review. `review` clears it, and nothing else does once `reviewed_at` exists.
6. `build` produces a single `index.html` that makes no network requests and works from `file://`. `build --check` detects stale output. Builds are byte-for-byte reproducible.
7. The page opens on an interactive relationship graph that supports:
   - neighbourhood focus at depths 1–3;
   - pan, zoom and pinning;
   - the hierarchy toggle;
   - the Health, Mud and Drift overlays;
   - a Vocabulary panel and legend that show definitions, with core kinds encoded identically in every project;
   - kind, status and relation filters shared with the list view;
   - redirecting search;
   - deep links that carry view state;
   - keyboard navigation;
   - both themes, the minimum 1280×720 viewport and reduced motion.
   All Playwright interaction tests pass.
7a. The visual design follows the "Visual design" section:
   - the design mockup was approved before implementation;
   - the token contrast, colour-blind and raw-value checks pass;
   - the manual design review against the five principles passes in both themes.
8. Layout is deterministic: identical positions across loads of the same build. The 300-concept fixture renders in under 2 s.
9. The isolation test passes: the project's Python environment files are unchanged. The packaging tests pass: the skill works when copied to any location, references nothing outside its own directory, contains no harness-specific features, conforms to the Agent Skills specification (`skills-ref validate`, `SKILL.md` under 500 lines, references one level deep), follows the script conventions (non-interactive, `--help`, `--dry-run`, documented exit codes), and maintains `AGENTS.md` idempotently.
10. In the sample-project scenarios, run in Cursor, the agent behaves as described in "Agent workflow", including never authoring definitions on its own.

## Open Questions

1. ~~**Distribution.**~~ **Resolved:** the skill is developed here, published to the agentic-toolkit repo, and copied into each project. It is harness-agnostic, with Cursor as the primary harness. See "Packaging and distribution".
2. ~~**Agent-suggested definitions.**~~ **Resolved:** keep `proposal.suggested_definition`. The rubber-stamping risk is accepted, consistent with the "soft B" stance in the intent. Suggestions stay labelled as the agent's and are never copied into `definition` by the agent.
3. ~~**Core vocabulary contents.**~~ **Resolved:** the core kinds are `entity`, `event`, `attribute` and `metric`; the core relation types are `is_a`, `part_of`, `attribute_of` and `related_to`. `attribute` was promoted to core, together with `attribute_of` to connect it. `metric` keeps its name (it's the team's own word) with a sharper definition: an aggregate over many instances, as distinct from an `attribute`.
4. ~~**Drift signal (W106).**~~ **Resolved:** W106 now combines checking only for changes near the symbol with an explicit `reviewed_at` record set by `review`. It's documented as a prompt to check, not a guarantee. See "Drift detection (W106)".
5. ~~**Committing `index.html`.**~~ **Resolved:** commit it, so fresh clones have the ontology ready to browse. Diff noise and merge conflicts are handled by reproducible output, an optional `.gitattributes` entry, and "rebuild to resolve conflicts".
6. ~~**Skill name.**~~ **Resolved:** `curating-the-ontology`. "Ontology curation" is the practitioners' term for ongoing, human-led stewardship of an ontology. The name is also the skill directory name and the `name` frontmatter field, as the Agent Skills format requires.
7. ~~**Second verification harness.**~~ **Resolved:** none. v1 behaviour is verified in Cursor only. The skill stays harness-agnostic by design (standard frontmatter, no harness-specific features, the `SKILL.md` lint in the packaging tests), but is not tested in other harnesses.
8. ~~**Graph engine: hand-written or vendored?**~~ **Resolved:** vendored D3 subset (`d3-selection`, `d3-force`, `d3-zoom`, `d3-drag`, `d3-shape` and their dependencies), pinned and checksummed, used for physics and gestures only. The hierarchy view uses a layered force to handle multiple parents. See the tech stack.
9. ~~**Layout stability across larger edits.**~~ **Resolved:** best effort only. Seeding positions from concept ids keeps the picture broadly familiar, but layouts may change as the model evolves, and sometimes they should. No positions are carried over from previous builds.
10. ~~**Toolkit conventions.**~~ **Resolved:** the toolkit has no conventions of its own yet, so it follows the [Agent Skills](https://agentskills.io/) specification and best practices. The spec now conforms to them:
    - frontmatter constraints;
    - the `scripts/`, `references/` and `assets/` layout;
    - a `SKILL.md` body under 500 lines;
    - relative references, one level deep;
    - non-interactive scripts with `--help`, `--dry-run` and documented exit codes;
    - `skills-ref validate` in the packaging tests.
