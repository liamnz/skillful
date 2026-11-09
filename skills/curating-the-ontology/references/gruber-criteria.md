# Gruber's criteria for a good ontology

Read this when critiquing a definition or explaining a finding's criterion. Thomas
Gruber (1995) set out five criteria for designing ontologies meant to be shared. The
validator tags each finding with the criterion it serves (`criterion` in
`validate --json`), plus two this skill adds for code-linked ontologies: drift and
staleness.

When you critique, quote the definition, name the criterion, and ask a question the
human can answer. Never rewrite the definition yourself.

## Clarity

A definition should communicate the intended meaning objectively and, where possible,
completely: necessary and sufficient conditions, in natural language, independent of
any one use.

- Good: *Active customer* — "A customer who has made at least one paid order in the
  trailing 90 days, regardless of subscription state."
- Bad: "An active user of the platform." (Circular, and "active" is the thing being defined.)
- Bad: "Customers we care about." (No condition anyone could check.)

Ask: "How would two people decide, independently, whether a given customer is active?"

Findings: W101 too short, W102 circular, W113 too many kinds to tell apart, I204
`related_to` is unnamed, E011 a defined extension without a definition.

## Coherence

The ontology should allow only inferences consistent with its definitions. Relations,
kinds and terms must not contradict one another.

- Bad: *Refund* `is_a` *Order* while the definitions say a refund reverses an order.
- Bad: "client" a discouraged term for Customer, and also the name of another concept.

Ask: "If X is a Y, is every X really a Y? Can you think of an X that isn't?"

Findings: E004 missing target, E005 unknown kind or type, E006 cycle in an acyclic
type, E007 one term with two meanings, E010 reused vocabulary id, E012 unknown kind in
from/to, E013 cardinality where it means nothing, E014 conflicting cardinality, W104
relation to a deprecated concept, W109 a discouraged term in use, W110 from/to broken,
W111 `is_a` across kinds, W112 deprecated vocabulary in use.

## Extendibility

New terms should be definable from the existing ones without revising them. Shared
foundations (a clear `Customer`) let others build narrower concepts (`Active customer`,
`Churned account`) without redefining the base.

- Good: a deprecated concept that names its replacement (`replaced_by`), so references
  and readers can follow it.
- Bad: three metrics that each restate their own idea of "paid order" instead of
  relating to one concept.

Ask: "Could someone define the next concept in terms of this one?"

Findings: I202 deprecated without `replaced_by`.

## Minimal encoding bias

The conceptualisation should be specified at the knowledge level, not shaped by how it
happens to be stored or computed. A definition describes the domain; `implemented_in`
says where the code lives.

- Good: "The total price charged for an order after discounts and before refunds."
- Bad: "`amount_net` from `fct_orders`, excluding rows where `is_test = 1`." (That is
  the implementation, and it will change.)

**Cardinality versus table grain.** Cardinality records what is true of the domain, not
the grain of a particular table. If the domain says each order belongs to one customer
but `fct_orders` allows several `customer_id`s per order, do not record `N:M` to match
the table, and do not silently keep `1:N` either: keep the domain fact and add an
`open_questions` entry ("`fct_orders` allows several customers per order; is that a
data error or a real case?"). The difference is often exactly the fan-out bug that
double-counts a metric.

Ask: "If the table were rebuilt differently tomorrow, would this definition still be true?"

Findings: W103 definition names its implementation.

## Minimal ontological commitment

Make as few claims about the world as the shared purpose needs. Define what the team
actually uses; leave the rest open rather than guess.

- Good: an `open_questions` entry instead of an invented rule; no cardinality when
  nobody knows it.
- Bad: a concept nothing relates to and no code implements, added "for completeness".

Ask: "Who needs this concept, and for what?"

Findings: I201 isolated concept, I203 unused vocabulary.

## Drift and staleness (added by this skill)

An ontology tied to code must stay true as the code changes, and proposals must not
linger undecided.

Findings: E009 `implemented_in` path missing, W105 symbol missing, W106 code changed
since the last review, I205 review commit not in history (drift); W107 a proposal older
than `stale_proposal_days` (staleness).

## Structural findings

E001 (YAML does not parse), E002 (schema violation), E003 (id does not match the file),
E008 (defined without a definition) and W108 (the explorer is stale) carry no criterion:
they are about the records themselves, not the conceptualisation.
