# Sample project: Acme Analytics

A small dbt-style warehouse for **Acme**, an online shop that sells coffee
and coffee subscriptions. It has a populated ontology in
[`docs/ontology/`](docs/ontology/), and is used for:

- the design mockup (`examples/design/mockup.html`);
- manual review of the HTML view;
- the Cursor evaluation scenarios (`examples/evals.md`).

It is development material only and is never copied into projects with the skill.
The SQL is illustrative: it is never run.

## What's in the ontology

22 concepts:

| Kind | Concepts |
|---|---|
| entity | Customer, Active customer, Churned account *(proposed)*, Client account *(deprecated)*, Product, Order, Order line, Subscription, Subscription plan |
| event | Order placed, Refund issued, Subscription started, Subscription cancelled |
| attribute | Order amount, Customer region, Plan price, Subscription status |
| metric | Gross revenue, Net revenue, Average order value, Monthly recurring revenue, Retention rate |

Extensions: `has` and `measures` (defined), `derived_from` (proposed).

## Deliberate imperfections

The ontology is meant to look like a real one in mid-life, so some mud is
intentional. Don't "fix" these without updating the tests and evals that rely on them.

| What | Where | Used by |
|---|---|---|
| **Definition contradicts the code.** Active customer says "trailing 90 days"; `dim_customer.sql` uses 30 days. No check can see this. | `active-customer.yaml`, `models/marts/dim_customer.sql` | Eval (d): the agent should challenge it. |
| A `proposed` concept with an agent suggestion | `churned-account.yaml` | Mud overlay, detail pane, eval (b) |
| A `proposed` relation type in use | `derived_from` on Net revenue | Mud overlay, Vocabulary panel |
| `related_to` instead of a named relationship | Subscription → Subscription plan | I204, Mud overlay, eval (f) |
| Open questions | Active customer, Subscription | Mud overlay |
| A deprecated concept with `replaced_by` | `client-account.yaml` | Faded rendering |
| Discouraged terms | Customer (client, shopper), Order (basket), Subscription (membership), Monthly recurring revenue (MRR, run rate) | Redirecting search, eval (e) |
| Cardinalities | `has` and `part_of` relations | Edge labels, detail-pane sentences |

## Expected findings

[`expected-findings.yaml`](expected-findings.yaml) lists every validator finding
this project may produce. `tests/test_sample_project.py` fails if `validate`
reports anything else, so a new check that fires here must be either a deliberate
imperfection (add it to the file) or a fix to the sample.
