# Workflow in detail

Commands below are written as `onto.py <command>`; run each as
`uv run --script $SKILL/scripts/onto.py <command>` from the project root.

## End-of-task proposals

The aim is to turn what was learned during a task into the shared vocabulary, without
getting in the way. One short message, at most three items, then back to the user.

**Gather.**
1. Run `onto.py impact --json`. It lists every changed file (committed since the
   branch left the default branch, plus uncommitted and untracked files), the concepts
   whose `implemented_in` points at each, and the changed files no concept points at.
2. Read the diff for what `impact` cannot see: new columns, renamed models, new
   filters or thresholds, a metric computed differently.

**Decide what is worth raising.** Rank by how much a newcomer would misunderstand
without it:
- a *changed* concept whose code changed meaning (a threshold, a filter, a grain);
- a *new* domain idea that has a name in the code but no concept (`is_churned`,
  `fct_refunds`);
- a term used for two things, or two terms for one thing.

Skip plumbing (staging models, renames with no change in meaning, formatting). An
unmapped file is a candidate, not a concept: decide whether it introduces a domain
idea.

**Write the message.** For example:

> Ontology: this change touches three concepts.
> - **Churned account** (new): `fct_churn.sql` adds `is_churned`; no concept covers it. Create a stub?
> - **Active customer**: `dim_customer.sql` now uses 30 days, the definition says 90. Which is right?
> - **Refund issued** has no `implemented_in`; `fct_refunds.sql` looks like it. Add the link?

**Act on the answer.**
- For a yes to a new concept: `onto.py new churned-account --name "Churned account"
  --kind entity --rationale "Introduced as is_churned in models/marts/fct_churn.sql"
  --implemented-in models/marts/fct_churn.sql:is_churned`. Add
  `--suggested-definition "..."` only if you have a useful starting point; it is shown
  as the agent's suggestion, apart from the definition.
- Then ask the user to write the definition in their own words. If they dictate it,
  copy it verbatim into `definition`, and set `status: defined` only when they say so.
- For a no: drop it. Do not raise it again in this task.
- Run `onto.py validate` and `onto.py build`.

**Cardinality suggestions.** Cardinality is a domain claim, like a definition. Suggest
one only with evidence, and say where it came from:

> `fct_orders` has exactly one `customer_id` per row and `order_id` is unique, so
> **Customer has Order `1:N`**? (Can an order ever be shared between customers?)

Write it into the relation only after the user confirms. If the code and the domain
disagree (the table allows several customers per order but the business says one),
record the domain fact and add an `open_questions` entry about the table; do not pick
silently.

## Reviews and drift

W106 means code near a concept's `implemented_in` symbol (or anywhere in the file,
without a symbol) changed since a human last confirmed the definition.

1. Read the diff the finding points at: `git diff <commit>..HEAD -- <path>` plus any
   uncommitted changes.
2. Tell the user what changed and ask whether the definition still holds.
3. If it holds, offer: "Record that with `onto.py review <id>`?" Run it only on a yes.
   `review` stores HEAD's commit in `reviewed_at`; `--path` limits it to one file.
4. If it does not hold, the user edits the definition (or dictates it). Then review.

`review` refuses (exit 3) while a reviewed path has uncommitted changes: commit the
code first, so the review is recorded against the code it describes. Editing the
concept file for another reason never clears W106 once `reviewed_at` exists. I205
means `reviewed_at` points at a commit no longer in history (after a rebase or
squash); a fresh review fixes it.

## Health check

1. Run `onto.py validate --json` (add `--limit 50` for very large ontologies).
2. Group the findings by `criterion`, most serious first: errors, then warnings, then
   info. Lead with what blocks understanding (E-codes, W102 circular definitions, W109
   discouraged terms in use), then drift (W105, W106), then housekeeping.
3. For each group, give the count and one or two concrete examples with the fix.
4. Offer fixes you may apply with consent: relation targets, `implemented_in` paths and
   symbols, discouraged terms, `replaced_by`. Definitions and statuses stay the user's.
5. After fixes, run `validate` again, then `build`.

Findings that point at the vocabulary (E010–E012, W110, W112, I203, and W107 on an
extension) have no concept; they concern `ontology.yaml`.

## Resolving conflicts

- **`index.html`:** take either side, resolve the YAML conflicts, run `onto.py build`,
  and commit the rebuilt file. Never hand-merge the HTML. `onto.py build --check` exits
  1 if the committed view is stale.
- **A concept file:** merge the YAML by meaning. If both sides changed the definition,
  do not choose: show the user both versions and ask them to write the result.
- **`ontology.yaml`:** keep both sides' extensions unless they share an id; then ask.
- After resolving, run `onto.py validate` and `onto.py build`.

## Starting an ontology

1. Run `onto.py init --dry-run` to show what would be created.
2. Ask the user about the `AGENTS.md` pointer and the `.gitattributes` line, then run
   `onto.py init --name "<Ontology name>"` with `--agents-md` or `--no-agents-md`, and
   `--gitattributes` or `--no-gitattributes`.
3. Suggest a first handful of concepts from the most central tables or models, and
   create stubs only for the ones the user picks.
