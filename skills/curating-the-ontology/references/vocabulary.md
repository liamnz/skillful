# Vocabulary: kinds and relation types

Read this before proposing a new kind or relation type, or when choosing between
existing ones. Kinds and relation types describe concepts, so they need the same care
as concepts: otherwise the synonym problem moves up a level (`related_to`,
`associated_with` and `linked_to`, each meaning whatever the reader assumes).

Run `onto.py vocab list` to see everything available, with status and usage counts.

## The core vocabulary

The core is identical in every project and cannot be removed or redefined. The tooling
relies on it (cycle checks, hierarchy layout, kind constraints, fixed colours and shapes).

| Kind | Meaning | Examples |
|---|---|---|
| `entity` | A thing the domain keeps track of over time, with an identity of its own. | Customer, Order |
| `event` | Something that happens at a point in time and is recorded. | Order placed, Subscription cancelled |
| `attribute` | A property of a single entity or event, with no identity of its own. | Customer region, Order amount |
| `metric` | A quantity computed by aggregating over many instances, to assess something. | Retention rate, Average order value |

A numeric property of one instance (an order's amount) is an `attribute`, not a
`metric`. A thing you count is an `entity` or `event`; the count is a `metric`.

| Relation type | Meaning | Notes |
|---|---|---|
| `is_a` | Every instance of the source is an instance of the target (subtype). | Acyclic, transitive. Inverse: `has_subtype`. Same kind on both ends. No cardinality. |
| `part_of` | The source is a component of the target and makes no sense without it. | Acyclic. Inverse: `has_part`. |
| `attribute_of` | The source attribute describes instances of the target. | From `attribute` to `entity` or `event`. Inverse: `has_attribute`. No cardinality. |
| `related_to` | A connection nobody has named precisely yet. | Symmetric. Each use is flagged (I204) as an invitation to name it. |

## Choosing

1. Prefer a core term. Most relations between things are `is_a`, `part_of` or
   `attribute_of`, or a domain verb the project has already declared.
2. Then an existing extension: check `vocab list`, including `proposed` ones.
3. Use `related_to` only as a placeholder, and ask the user what the relationship is.

## Proposing an extension

Propose one only when nothing fits, and say why:

```bash
uv run --script $SKILL/scripts/onto.py vocab new relation measures \
  --inverse measured_by --from metric --to entity event \
  --rationale "Metrics summarise entities and events; no core type says how."
uv run --script $SKILL/scripts/onto.py vocab new kind rule \
  --rationale "Business policies recur across models and are neither entities nor attributes."
```

- The extension is added as `proposed` with an empty definition. Ask the user to define
  it in their own words; until then it shows as needing a definition.
- A relation type needs an `inverse` label (how it reads from target to source). Add
  `--acyclic` if it must never loop (like `derived_from`), and `--from`/`--to` if only
  some kinds make sense at each end; the validator then enforces them (W110).
- `vocab new` refuses core ids and existing ids (exit 3), and leaves the rest of
  `ontology.yaml` untouched.
- New `init` manifests carry commented-out starters (`rule`, `has`, `derived_from`,
  `measures`). Suggest uncommenting one before inventing a near-duplicate.

## Challenging near-duplicates

Before accepting a new term, compare it with what exists:

- Same meaning, different word (`linked_to` vs `related_to`, `contains` vs `has_part`):
  use the existing one.
- Narrower meaning (`places` vs a generic `has`): worth it only if the difference
  matters to someone reading the graph; ask "would anyone draw a different conclusion?"
- Different direction only (`owned_by` vs `owns`): that is an inverse label, not a new
  type.

## Retiring vocabulary

Set an extension's `status: deprecated` (a human decision). Concepts and relations that
still use it are flagged (W112); move them to another term, then the extension can be
removed. Unused extensions are flagged (I203). More than eight kinds in use (W113) means
the graph can no longer give each kind its own colour and shape: merge or retire kinds.
