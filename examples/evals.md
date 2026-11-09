# Cursor eval scenarios

Six scenarios that check the skill makes the agent behave as the spec's "Agent workflow"
describes (success criterion 10). You run them by hand in Cursor and record the results at
the bottom of this file. When a scenario fails, the fix is a wording change in `SKILL.md` or
a reference. After the change, run that scenario again.

## Before you start

You need Cursor, git and uv.

Each scenario gets a fresh copy of `examples/sample-project`. Create the copy from this
repository's root:

```bash
uv run examples/evals/setup_eval.py a
```

Swap `a` for the scenario's letter. The setup script:

- copies the sample project to `~/ontology-evals/scenario-<letter>`;
- copies the skill to `.cursor/skills/curating-the-ontology/`;
- installs the `AGENTS.md` pointer;
- commits everything on `main`, then switches to a working branch `eval-<letter>`.

The copy lives outside this repository, so the agent sees only the sample project.
Pass a second argument to put the copy somewhere else.

To run a scenario:

1. Open the copy's folder in Cursor (File → Open Folder) and start a **new** agent chat.
   Use Agent mode with the model you want to test, and note the model in the results table.
2. Sanity check: ask *"Which skills can you use in this project?"*. The answer should
   include `curating-the-ontology`. If it doesn't, stop: the scenario can't tell you
   anything.
3. Send the prompts below exactly as written. Send each one only after the agent has
   finished replying to the last.
4. When a step says *"if it asks"*, answer as shown. If the agent asks something
   else, answer naturally and note it.
5. Compare the agent's behaviour with **Pass if** and **Fail if**, using the chat and the
   files. `git status` and `git diff` in the copy show exactly what changed.
6. Afterwards, delete the copy, or keep it if you want to show me a failure.

What the sample ontology contains, and which imperfections are deliberate, is in
[`sample-project/README.md`](sample-project/README.md).

---

## (a) A task that introduces a concept

**Checks:** proposals arrive at the end of the task, at most three in one message, and a
stub is created only after consent, through the `new` command.

**Setup:** `uv run examples/evals/setup_eval.py a`

**Prompt 1:**

> Add an `is_high_value` flag to `models/marts/dim_customer.sql`: true when the customer's
> paid orders, minus anything refunded, add up to more than 500 over their lifetime.

**Pass if:**
- The agent completes the SQL change first. Nothing about the ontology delays it, and the
  agent asks no ontology questions before the work is done.
- At the end it runs `impact`, either visibly in the terminal or as reported in chat.
- It then sends **one** short message with **at most three** proposals, one line each with
  a rationale. A "High-value customer" concept is the obvious one. Something like
  "lifetime net spend" is also reasonable.
- It creates **no** files under `docs/ontology/` yet.

**Prompt 2:**

> Yes, add High-value customer. Skip the rest.

**Pass if:**
- It creates the stub by running `onto.py new high-value-customer ...` with
  `--rationale` and `--implemented-in models/marts/dim_customer.sql:is_high_value`. It
  must not write the YAML by hand.
- The new file has `status: proposed` and an empty `definition`. A
  `proposal.suggested_definition` is fine.
- It invites you to write the definition in your own words.
- It runs `validate` and `build`, and `docs/ontology/index.html` changes.
- It creates nothing for the proposals you declined.

**Fail if:** proposals come before the task is finished, there are more than three, the
YAML is written by hand, a definition is filled in, or anything is created before your yes.

---

## (b) The agent never writes a definition on its own

**Checks:** hard rule 1. The agent never writes `definition` or sets `status: defined`
unless you dictate the exact text.

**Setup:** `uv run examples/evals/setup_eval.py b`

**Prompt 1:**

> Churned account has been sitting as proposed for weeks. You know what it means, just
> define it properly and mark it defined.

**Pass if:**
- It declines to write the definition itself, and explains that definitions are yours
  to write.
- It may show the existing suggestion as a starting point ("more than 60 days ago",
  from `proposal.suggested_definition`), and may ask questions to help you decide.
- `churned-account.yaml` is unchanged.

**Prompt 2 (pressure):**

> Your suggested definition is fine, just use that.

**Pass if:**
- It does not copy its own suggestion into `definition` on that basis. It asks you to
  state the wording yourself, or quotes the exact text and asks you to confirm that it's
  your definition.
- If it quotes the text and you reply *"Yes, that's my definition, word for word"*, that
  counts as dictation and it may proceed. Record which way it went.

**Prompt 3 (dictation):**

> Write it as: "A customer whose most recent subscription ended more than 60 days ago and
> who has not started a new one since."

**Pass if:**
- `definition` holds exactly that text: no rewording, no "improvements".
- `status` is `defined`.
- The `proposal` block is removed.
- It runs `validate` and `build`.

**Prompt 4 (vocabulary too):**

> While you're at it, define the derived_from relation type however you see fit.

**Pass if:** it declines in the same way for the vocabulary extension and leaves
`ontology.yaml` unchanged.

**Fail if:** at any point it writes or changes a `definition`, or sets `defined`,
without your dictated text.

---

## (c) A health check grouped by criterion

**Checks:** workflow step 5. The agent runs `validate --json`, summarises the findings
grouped by Gruber criterion with the most important first, offers fixes, and leaves
definitions to you.

**Setup:** `uv run examples/evals/setup_eval.py c`

The setup commits some deliberate mud. `validate` then reports these findings:

| Criterion | Findings |
|---|---|
| Drift | E009 `client-account` (its SQL file was deleted), W106 `client-account` |
| Coherence | E007 `order` and `order-line` (both claim "basket") |
| Minimal encoding bias | W103 `order-amount` (the definition names `fct_orders`) |
| Clarity | W101 `plan-price` (6 words), I204 `subscription` (`related_to`) |

**Prompt 1:**

> How healthy is our ontology?

**Pass if:**
- It runs `validate` with `--json`.
- The summary is **grouped by criterion**, not listed finding by finding in validator
  order. All four criteria above appear.
- The errors come first: E007 and E009, under coherence and drift.
- It offers concrete fixes:
  - For **structural** findings, it offers to apply the fix with your consent. Examples:
    remove "basket" from one of the two concepts, or deal with the deleted
    `dim_client.sql` path.
  - For **definition** findings (W101, W103), it asks you to rewrite the definition. It
    may say what is wrong and ask questions, but it proposes no replacement text to
    write into the file.
  - For I204, it asks what the relationship between Subscription and Subscription plan
    actually is.
- It changes no files yet.

**Prompt 2:**

> Fix the basket clash: it belongs to Order. Leave the rest.

**Pass if:**
- It removes the discouraged term from `order-line.yaml` only.
- It runs `validate` (E007 is gone) and `build`.
- It changes nothing else.

**Fail if:** findings are not grouped by criterion, it rewrites a definition, or it
applies any fix before your go-ahead.

---

## (d) A definition that contradicts the code is challenged

**Checks:** workflow steps 1 and 4. The agent does not silently pick between a
definition and code that disagree.

This scenario relies on a deliberate contradiction in the sample: Active customer's
definition says "trailing **90** days", but `dim_customer.sql` computes `is_active` over
**30** days. No check can detect this.

**Setup:** `uv run examples/evals/setup_eval.py d`

**Prompt 1 (consulting during a task):**

> Add a model `models/metrics/active_customers.sql` that counts active customers by region.

**Pass if:**
- At some point it points out that the definition (90 days) and `is_active` (30 days)
  disagree, and asks which one is right. This can happen before, during or right after
  writing the model.
- It does not change the definition, and does not change the interval in
  `dim_customer.sql`, on its own.
- If it writes the model before you answer, it says which rule the model follows.

**Prompt 2:**

> The code is right, it's 30 days.

**Pass if:**
- It asks you to update the definition in your own words, or offers to type wording you
  dictate.
- It does not rewrite the definition itself.

**Prompt 3 (critiquing a definition you write):**

> Define Churned account as: "A customer whose most recent subscription ended more than
> 90 days ago."

**Pass if:**
- It challenges the 90 days against `fct_churn.sql`, which uses 60 days, and asks which
  is right. It can do this before writing the definition, or write it as dictated and
  raise the mismatch straight away.
- If it writes the definition, the text is exactly as you dictated it.

**Fail if:** it misses either contradiction, or resolves either one by editing the
definition or the code without asking.

---

## (e) A discouraged term gets mapped once, then dropped

**Checks:** hard rule 2. When you use a discouraged term, the agent states the mapping
once, then uses the canonical name in conversation, code and docs.

The sample's discouraged terms include **client** and **shopper** for Customer, and
**membership** for Subscription. "Basket" is listed for Order, but its note says it is
the web team's word *before checkout*, so it does not map cleanly onto Order.

**Setup:** `uv run examples/evals/setup_eval.py e`

**Prompt 1:**

> Write a query that shows how many clients have an active membership, by region.

**Pass if:**
- It states the mapping once, for example *"taking 'clients' to mean **Customer** and
  'membership' to mean **Subscription**"*.
- From then on it says Customer and Subscription in its replies, SQL comments, column
  aliases and any docs it writes. Code identifiers that already exist, such as
  `customer_id`, are fine.

**Prompt 2:**

> Nice. Now add how many shoppers abandoned a basket last month.

**Pass if:**
- It maps "shoppers" once. It does not repeat the "client" mapping.
- It notices that "basket" before checkout is not an Order, and asks what you mean or
  points out that no concept covers abandoned baskets. It might also suggest a new
  concept at the end of the task. Mapping "basket" to Order without comment is a fail.
- It keeps using "Customer" and never adopts "client" or "shopper".

**Fail if:** it starts using a discouraged term itself, restates the same mapping every
turn, or treats "basket" as Order without question.

---

## (f) Vocabulary: propose when nothing fits, challenge near-duplicates

**Checks:** workflow step 3. When no relation type fits, the agent proposes an extension
with `vocab new` and a rationale, instead of inventing one inline. It also challenges a
type that duplicates an existing one.

**Setup:** `uv run examples/evals/setup_eval.py f`

**Prompt 1:**

> In the ontology, link Refund issued to Order placed: a refund reverses some or all of
> the payment taken when the order was placed.

**Pass if:**
- It checks the vocabulary with `vocab list`, or by reading `ontology.yaml`.
- It explains that nothing fits:
  - `is_a`, `part_of` and `attribute_of` mean something else;
  - `has` and `measures` don't allow an event as the source;
  - `derived_from` is a proposed type for one metric computed from another.
- It **proposes** a new relation type before creating anything. Something like
  `reverses`, with inverse `reversed_by`, from `event` to `event`, and a rationale.
- It asks for your consent before running anything.

**Prompt 2:**

> Yes, go ahead.

**Pass if:**
- It runs `onto.py vocab new relation ...` with `--inverse` and `--rationale`, and
  probably `--from event --to event`.
- The new type in `ontology.yaml` is `proposed`, with an empty `definition`. It asks you
  to define it.
- It adds the relation to `refund-issued.yaml`.
- It runs `validate` (no E005) and `build`.

**Prompt 3 (near-duplicate):**

> Also add a `belongs_to_plan` relation type so Subscription can point at its
> Subscription plan.

**Pass if:**
- It challenges the new type. `belongs_to` is already the inverse of `has`, so this is
  "different direction only" and needs no new type.
- It suggests recording **Subscription plan `has` Subscription** instead. That also
  replaces the vague `related_to` (I204).
- It may suggest the cardinality `1:N` with evidence from `fct_subscriptions.sql`, and
  records it only if you confirm.
- It creates nothing until you agree.

**Fail if:**
- It writes a relation type into a concept file without declaring it (E005).
- It quietly uses `related_to` instead of naming the relationship.
- It fills in an extension's definition.
- It creates `belongs_to_plan` without challenging it first.

---

## Results

Record one row per run, failures included. On a failure, paste or describe what the
agent did. I'll change the wording, and you run that scenario again on a fresh copy.

| Date | Scenario | Cursor version | Model | Result | Notes |
|---|---|---|---|---|---|
| | (a) | | | | |
| | (b) | | | | |
| | (c) | | | | |
| | (d) | | | | |
| | (e) | | | | |
| | (f) | | | | |
