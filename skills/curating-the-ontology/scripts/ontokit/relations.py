"""Relation checks: E004, E006, E013, E014, W104, W111 and I204.

Relations whose type is neither core nor a declared extension are left to E005
(vocabcheck.py); these checks skip them rather than guess what they mean.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator

from .context import Context
from .findings import Finding, finding
from .io import Concept, Ontology, Relation

SYMMETRIC_CARDINALITIES = ("1:1", "N:M")


def check_relations(ontology: Ontology, ctx: Context) -> Iterator[Finding]:
    yield from _targets(ontology)
    yield from _cardinality(ontology)
    yield from _conflicts(ontology)
    yield from _cycles(ontology)


def _known(ontology: Ontology, concept: Concept) -> Iterator[Relation]:
    """The concept's relations whose type is known and whose target exists."""
    types = ontology.relation_types
    for relation in concept.relations:
        if relation.type in types and relation.target in ontology.concepts:
            yield relation


def _targets(ontology: Ontology) -> Iterator[Finding]:
    """E004 missing target, W104 deprecated target, W111 is_a across kinds, I204 related_to."""
    concepts = ontology.concepts
    for concept in concepts.values():
        for relation in concept.relations:
            target = concepts.get(relation.target)
            if target is None:
                yield finding(
                    "E004",
                    concept.id,
                    f"Relation '{relation.type}' targets '{relation.target}', which is not a concept. "
                    f"Fix the id, or propose it with 'onto.py new {relation.target} ...'.",
                )
                continue
            if target.status == "deprecated" and concept.status != "deprecated":
                instead = f" Point it at '{target.replaced_by}' instead." if target.replaced_by else ""
                yield finding(
                    "W104",
                    concept.id,
                    f"Relation '{relation.type}' targets '{target.id}', which is deprecated.{instead}",
                )
            if relation.type == "is_a" and target.kind != concept.kind:
                yield finding(
                    "W111",
                    concept.id,
                    f"'{concept.id}' ({concept.kind}) is_a '{target.id}' ({target.kind}): a subtype should be "
                    "the same kind as its parent. Check the kinds, or use a different relation type.",
                )
            if relation.type == "related_to":
                yield finding(
                    "I204",
                    concept.id,
                    f"'{concept.id}' related_to '{target.id}': can this relationship be named more precisely?",
                )


def _cardinality(ontology: Ontology) -> Iterator[Finding]:
    """E013: cardinality where the relation type does not allow it."""
    types = ontology.relation_types
    for concept in ontology.concepts.values():
        for relation in concept.relations:
            spec = types.get(relation.type)
            if relation.cardinality is None or spec is None:
                continue
            if spec.get("cardinality_allowed", True) is False:
                yield finding(
                    "E013",
                    concept.id,
                    f"Relation '{relation.type}' to '{relation.target}' has cardinality '{relation.cardinality}', "
                    f"but cardinality means nothing on '{relation.type}'. Remove it.",
                )
            elif spec.get("symmetric") and relation.cardinality not in SYMMETRIC_CARDINALITIES:
                yield finding(
                    "E013",
                    concept.id,
                    f"Relation '{relation.type}' to '{relation.target}' has cardinality '{relation.cardinality}', "
                    f"but '{relation.type}' is symmetric, so only {' or '.join(SYMMETRIC_CARDINALITIES)} "
                    "can be read the same way in both directions.",
                )


def _conflicts(ontology: Ontology) -> Iterator[Finding]:
    """E014: the same relationship stated more than once with different cardinalities.

    A relationship is (source, type, target); for a symmetric type the two ends are
    unordered, so a statement on each concept is the same relationship.
    """
    types = ontology.relation_types
    stated: dict[str, list[tuple[str, str]]] = defaultdict(list)  # relationship -> [(source, cardinality)]
    for concept in ontology.concepts.values():
        for relation in _known(ontology, concept):
            if relation.cardinality is None:
                continue
            source, target = concept.id, relation.target
            if types[relation.type].get("symmetric"):
                source, target = sorted((source, target))
            stated[f"'{source}' {relation.type} '{target}'"].append((concept.id, relation.cardinality))
    for what, statements in sorted(stated.items()):
        if len({cardinality for _, cardinality in statements}) < 2:
            continue
        where = ", ".join(f"{cardinality} on '{source}'" for source, cardinality in sorted(statements))
        for source in sorted({source for source, _ in statements}):
            yield finding(
                "E014",
                source,
                f"{what} is stated with conflicting cardinalities ({where}). Keep one statement with the "
                "cardinality that is true of the domain.",
            )


def _cycles(ontology: Ontology) -> Iterator[Finding]:
    """E006: a cycle in any acyclic relation type, core or extension. Each cycle is reported once."""
    for type_id, spec in sorted(ontology.relation_types.items()):
        if not spec.get("acyclic"):
            continue
        edges: dict[str, list[str]] = {
            concept.id: sorted({r.target for r in _known(ontology, concept) if r.type == type_id})
            for concept in ontology.concepts.values()
        }
        for cycle in _find_cycles(edges):
            path = " → ".join([*cycle, cycle[0]])
            yield finding(
                "E006",
                cycle[0],
                f"'{type_id}' must not loop, but it does: {path}. Remove or retarget one of these relations.",
            )


def _find_cycles(edges: dict[str, list[str]]) -> list[list[str]]:
    """One representative cycle per strongly connected component (Tarjan), deterministic.

    Each cycle starts at the smallest id in its component, so the same records always
    give the same message.
    """
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def connect(node: str) -> None:  # recursion depth is bounded by the ontology's size
        index[node] = low[node] = len(index)
        stack.append(node)
        on_stack.add(node)
        for nxt in edges.get(node, ()):
            if nxt not in index:
                connect(nxt)
                low[node] = min(low[node], low[nxt])
            elif nxt in on_stack:
                low[node] = min(low[node], index[nxt])
        if low[node] == index[node]:
            component = []
            while True:
                member = stack.pop()
                on_stack.discard(member)
                component.append(member)
                if member == node:
                    break
            if len(component) > 1 or node in edges.get(node, ()):  # a self-loop is a cycle too
                components.append(sorted(component))

    for node in sorted(edges):
        if node not in index:
            connect(node)

    cycles = []
    for component in sorted(components):
        members = set(component)
        cycles.append(_walk(component[0], edges, members))
    return cycles


def _walk(start: str, edges: dict[str, list[str]], members: set[str]) -> list[str]:
    """A shortest cycle through `start` inside one component (breadth-first, smallest ids first)."""
    previous: dict[str, str] = {}
    queue = [start]
    while queue:
        node = queue.pop(0)
        for nxt in edges.get(node, ()):
            if nxt not in members:
                continue
            if nxt == start:
                path = [node]
                while path[-1] != start:
                    path.append(previous[path[-1]])
                return list(reversed(path))
            if nxt not in previous:
                previous[nxt] = node
                queue.append(nxt)
    return [start]  # unreachable: every component has a cycle through each member
