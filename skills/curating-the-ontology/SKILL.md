---
name: curating-the-ontology
description: >-
  Curates a human-owned domain ontology kept in docs/ontology/: proposes new or
  changed domain concepts at the end of coding tasks, critiques human-written
  definitions against the code, runs health checks for consistency and drift, and
  builds the ontology explorer, an interactive HTML graph of the concepts. Use when working in a repo that
  has docs/ontology/, when a task introduces or changes domain terms, data models,
  metrics or business rules, or when the user mentions the ontology, domain
  concepts, glossary, definitions, terminology or what a domain term means.
compatibility: Requires git and uv (uv provides Python 3.11+ and script dependencies).
metadata:
  version: "1.0.1"
---

# Curating the ontology

The ontology in `docs/ontology/` is the team's shared mental model of the domain: one
YAML file per concept, each defined **by a person**. Your job is to keep it honest and
in use: notice when work touches a concept, propose what is missing, question
definitions that disagree with the code, and keep the ontology explorer built. You never decide
what a concept means.

## Hard rules

1. **Humans write definitions.** Never write or change a `definition`, or set
   `status: defined`, for a concept or a vocabulary extension, on your own. You may
   type a definition into a file only when the user dictates the text in the
   conversation; copy it word for word (fix typos only if they agree).
2. **Canonical terms only.** In code, docs and conversation, use each concept's
   `name`. When someone uses a discouraged term, state the mapping once ("taking
   'active user' to mean **Active customer**") and use the canonical name from then on.
3. **Consent first.** Create stubs, propose vocabulary, apply structural fixes, edit
   `AGENTS.md` or `.gitattributes` only after the user agrees. Proposals never block
   or delay the user's task; if they decline, drop it.
4. **Never run `review` unconfirmed.** `review` records a human's claim that a
   definition still matches the code. Run it only after the user confirms that.
5. **Change records through the scripts** (`new`, `vocab new`, `review`). Edit YAML by
   hand only for fields no command sets (relations, `implemented_in`, discouraged
   terms, examples), and read [references/schema.md](references/schema.md) first.

## Running the scripts

`$SKILL` is the directory that contains this `SKILL.md`, wherever it was copied.
Run every command from the project root (the repository root), exactly like this:

```bash
uv run --script $SKILL/scripts/onto.py <command> [options]
```

`uv run --script` keeps the scripts out of the project's own Python environment.
Commands never prompt; ask the user in the conversation and pass their answer as a
flag. Every command has `--help` with examples. Results go to stdout, notes to stderr.

| Command | What it does |
|---|---|
| `init [--name N] [--agents-md\|--no-agents-md] [--gitattributes\|--no-gitattributes]` | Scaffold `docs/ontology/` |
| `new <id> --name N --kind K [--rationale R] [--suggested-definition D] [--implemented-in path[:symbol]]...` | Create a `proposed` concept stub |
| `vocab list [--json]` | Kinds and relation types, with status and usage |
| `vocab new kind <id> --rationale R` | Propose a kind extension |
| `vocab new relation <id> --inverse L [--acyclic] [--from K...] [--to K...] --rationale R` | Propose a relation type |
| `validate [--json] [--strict] [--limit N]` | Health check |
| `impact [--base REF] [--json] [--limit N]` | Concepts touched by changed files, and unmapped files |
| `review <id> [--path P]` | Record a confirmed review at HEAD |
| `build [--check]` | Write `docs/ontology/index.html` |

Write commands accept `--dry-run`. `--root PATH` points at an ontology elsewhere.
Exit codes: `0` success; `1` findings with errors (or warnings with `--strict`), or a
stale build with `--check`; `2` usage error; `3` refused (id exists, core id, broken
markers); `4` environment (no ontology, not a git repository, unknown base branch,
unsupported `schema_version`).

## Workflow

### 1. Consult

When you work in a repository with `docs/ontology/`, read the concepts relevant to
the task (`docs/ontology/concepts/<id>.yaml`) and use their names and definitions as
your working vocabulary. If the code you read or write contradicts a definition, say
so and ask which is right; do not silently pick one. A term in use that does not map
cleanly onto a concept is a candidate new concept, not a synonym.

### 2. End-of-task proposals

After a task that changed code:

1. Run `impact`. Combine its output with what you know from the diff.
2. Send **one short message** naming at most **three** new or changed concepts, one
   line each with its rationale. Mention concepts whose code changed ("review these
   definitions") and unmapped files that introduce a domain idea. Say nothing if
   nothing is worth raising.
3. If the user agrees, create stubs with `new` (never by writing YAML), including
   `--rationale` and `--implemented-in`. You may add `--suggested-definition`; it is
   shown as an agent suggestion, never as the definition.
4. Invite the user to write the definition in their own words.
5. You may suggest a relation's cardinality with its evidence ("`fct_orders` has one
   `customer_id` per order, so Customer has Order `1:N`?"). Record it only after
   they confirm.

Details and examples: [references/workflow.md](references/workflow.md).

### 3. Vocabulary

Kinds and relation types are vocabulary too. Before using or proposing one, run
`vocab list` and use a core term or an existing extension if one fits. Only if none
fits, propose one with `vocab new` and a rationale saying why the existing terms do
not fit. Challenge near-duplicates ("is `linked_to` different from `related_to`?").
When you see `related_to`, ask what the relationship actually is.
Read [references/vocabulary.md](references/vocabulary.md) before proposing a kind or
relation type.

### 4. Critique

When a human writes or edits a definition, check it against the code in
`implemented_in`, the related concepts and the Gruber criteria, and ask pointed
questions ("your definition says 90 days; `fct_retention.sql` uses 30 — which is
right?"). Read [references/gruber-criteria.md](references/gruber-criteria.md) before
critiquing a definition.

When a W106 drift finding or a changed file leads to a discussion and the user
confirms the definition still holds, offer to record it with `review <id>`.

### 5. Health check (on demand)

Run `validate --json`. Summarise the findings grouped by criterion, most important
first, and offer concrete fixes. Structural fixes (relations, paths, discouraged
terms) may be applied with consent; definitions stay the user's to write.

### 6. Rebuild

After any change to the ontology, run `validate`, then `build`, and commit the YAML
and `index.html` together.

### 7. Init

If the user asks to start an ontology and none exists, run `init`. Ask whether to add
the `AGENTS.md` pointer, explaining that without it the end-of-task proposals depend on
the skill happening to be loaded; pass `--agents-md` or `--no-agents-md` accordingly.
Ask the same about `--gitattributes`, which hides the generated `index.html` from diffs.

## Gotchas

- **Merge conflict in `index.html`:** never merge the HTML by hand. Resolve the YAML,
  run `build`, and commit the result.
- **No prompts:** commands read nothing from stdin. If one seems to wait, it is not
  this tool; never pipe answers into it.
- **Exit code 1 from `validate` means errors exist**, not that the command failed.
  Read the findings. Warnings alone exit `0` unless you pass `--strict`.
- **`review` refuses (exit 3) while a reviewed file has uncommitted changes.** Commit
  the code first, then review.
- **`impact` exits 4 when it cannot tell the default branch.** Pass `--base <branch>`.
- **Large outputs:** use `--limit` with `validate` and `impact` on big ontologies.
- **IDs:** concept ids are kebab-case (`active-customer`) and equal the file name;
  vocabulary ids are snake_case (`derived_from`).
- **Never edit `docs/ontology/index.html`.** It is generated; `build` rewrites it.

## References

- [references/workflow.md](references/workflow.md): read before making end-of-task
  proposals, recording a review, running a health check or resolving a conflict.
- [references/schema.md](references/schema.md): read before creating or editing a
  concept or the manifest by hand.
- [references/vocabulary.md](references/vocabulary.md): read before proposing a new
  kind or relation type, or when choosing between existing ones.
- [references/gruber-criteria.md](references/gruber-criteria.md): read when critiquing
  a definition or explaining a finding's criterion.
