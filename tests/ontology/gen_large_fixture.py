"""Generate the 300-concept, 600-relation scale fixture (deterministic).

Twelve clusters model a realistic analytics domain: each has a hub entity with subtypes
(is_a), parts (part_of), attributes (attribute_of), events (has) and metrics (measures),
and a seeded share of extra relations links clusters together. The records carry no
errors, so the explorer shows structure rather than validator noise.

    python tests/ontology/gen_large_fixture.py            # writes tests/ontology/fixtures/large (git-ignored)
"""

from __future__ import annotations

import random
import shutil
from pathlib import Path

CLUSTERS = [
    "account", "billing", "catalog", "campaign", "delivery", "inventory",
    "payment", "pricing", "returns", "session", "support", "warehouse",
]  # fmt: skip
SEED = 300
CONCEPTS = 300
RELATIONS = 600
PER_CLUSTER = CONCEPTS // len(CLUSTERS)  # 25
# Roles in each cluster (25 in all): kind and how the concept attaches to its cluster.
ROLES = (
    [("entity", "hub")]
    + [("entity", "subtype")] * 4
    + [("entity", "part")] * 5
    + [("attribute", "attribute")] * 6
    + [("event", "event")] * 5
    + [("metric", "metric")] * 4
)
MANIFEST = """schema_version: 1
name: Large fixture
description: A generated 300-concept ontology for scale and legibility checks.

extensions:
  relation_types:
    has:
      status: defined
      definition: >
        The source entity is associated with instances of the target over time,
        as in a customer has orders.
      inverse: belongs_to
      from: [entity]
      to: [entity, event]
    measures:
      status: defined
      definition: >
        The source metric is computed from instances of the target and
        summarises some aspect of them.
      inverse: measured_by
      from: [metric]
      to: [entity, event]
"""


def _definition(kind: str) -> str:
    return f"A generated {kind} that stands in for a real concept, so the view can be checked at scale."


def generate(dest: Path) -> Path:
    """Write docs/ontology/ under `dest` and return the ontology directory."""
    rnd = random.Random(SEED)
    root = dest / "docs" / "ontology"
    if root.exists():
        shutil.rmtree(root)
    (root / "concepts").mkdir(parents=True)
    (root / "ontology.yaml").write_text(MANIFEST, encoding="utf-8", newline="\n")

    concepts: dict[str, dict] = {}
    by_cluster: dict[str, list[str]] = {}
    for cluster in CLUSTERS:
        ids = []
        for n, (kind, role) in enumerate(ROLES):
            cid = cluster if role == "hub" else f"{cluster}-{role}-{n:02d}"
            name = cluster.capitalize() if role == "hub" else f"{cluster.capitalize()} {role} {n:02d}"
            concepts[cid] = {"id": cid, "name": name, "kind": kind, "role": role, "cluster": cluster, "relations": []}
            ids.append(cid)
        by_cluster[cluster] = ids

    def relate(source: str, type_: str, target: str) -> bool:
        pair = (type_, target)
        rels = concepts[source]["relations"]
        if source == target or pair in rels:
            return False
        rels.append(pair)
        return True

    # One structural relation per non-hub concept: 288.
    for ids in by_cluster.values():
        hub = ids[0]
        entities = [i for i in ids if concepts[i]["kind"] == "entity"]
        events = [i for i in ids if concepts[i]["kind"] == "event"]
        for cid in ids[1:]:
            role = concepts[cid]["role"]
            if role == "subtype":
                relate(cid, "is_a", hub)
            elif role == "part":
                relate(cid, "part_of", hub)
            elif role == "attribute":
                relate(cid, "attribute_of", rnd.choice(entities + events))
            elif role == "event":
                relate(hub, "has", cid)
            else:
                relate(cid, "measures", rnd.choice([hub, *events]))

    # Extra relations up to 600: mostly within a cluster, some across (hub to hub, metric to anything).
    total = sum(len(c["relations"]) for c in concepts.values())
    all_ids = sorted(concepts)
    while total < RELATIONS:
        cluster = rnd.choice(CLUSTERS)
        ids = by_cluster[cluster]
        across = rnd.random() < 0.1
        pool = all_ids if across else ids
        source = rnd.choice(ids)
        kind = concepts[source]["kind"]
        targets = [t for t in pool if concepts[t]["kind"] in ("entity", "event")]
        if kind == "metric":
            ok = relate(source, "measures", rnd.choice(targets))
        elif kind == "attribute":
            ok = relate(source, "attribute_of", rnd.choice(targets))
        elif kind == "entity":
            ok = relate(source, "has", rnd.choice([t for t in targets if t != source]))
        else:
            ok = relate(source, "related_to", rnd.choice([t for t in pool if concepts[t]["kind"] == "event"]))
        total += ok

    for c in concepts.values():
        lines = [
            f"id: {c['id']}",
            f"name: {c['name']}",
            f"kind: {c['kind']}",
            "status: defined",
            f"definition: {_definition(c['kind'])}",
            "relations:",
            *(f"  - {{type: {t}, target: {target}}}" for t, target in c["relations"]),
        ]
        if not c["relations"]:
            lines[-1] = "relations: []"
        (root / "concepts" / f"{c['id']}.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return root


if __name__ == "__main__":
    out = generate(Path(__file__).resolve().parent / "fixtures" / "large")
    print(f"wrote {out}")
