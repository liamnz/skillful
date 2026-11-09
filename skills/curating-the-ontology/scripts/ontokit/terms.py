"""Term and definition checks: E007, E008, W101, W102, W103, W109, I201 and I202.

Term matching is case-insensitive and whole-word. A "word" character is a letter,
digit or underscore, so "customer" matches "Customer", "a customer's" and
"customer-region", but not "customers" or "customers_raw". Whitespace inside a
term matches any run of whitespace, so "active  customer" across a line break
still matches "active customer".
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Iterator
from functools import cache
from pathlib import PurePosixPath

from .context import Context
from .findings import Finding, finding
from .io import Concept, Ontology

_SENTENCE_END = re.compile(r"(?<=[.!?])\s")


def normalise(term: str) -> str:
    """The form two terms are compared in: case-folded, whitespace collapsed."""
    return " ".join(term.split()).casefold()


@cache
def _pattern(term: str) -> re.Pattern[str]:
    words = [re.escape(w) for w in term.split()]
    return re.compile(r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)", re.IGNORECASE)


def mentions(text: str, term: str) -> bool:
    """True if `text` contains `term` as a whole word (or whole phrase), ignoring case."""
    return bool(term.strip()) and _pattern(term).search(text) is not None


def first_sentence(text: str) -> str:
    return _SENTENCE_END.split(text.strip(), maxsplit=1)[0]


def own_terms(concept: Concept) -> list[str]:
    return [concept.name, *(t.term for t in concept.discouraged_terms)]


def check_terms(ontology: Ontology, ctx: Context) -> Iterator[Finding]:
    yield from _shared_terms(ontology)
    yield from _discouraged_in_use(ontology)
    incoming = {r.target for c in ontology.concepts.values() for r in c.relations}
    min_words = ontology.settings.min_definition_words
    for concept in ontology.concepts.values():
        yield from _definition(concept, min_words)
        yield from _commitment(concept, incoming)


def _shared_terms(ontology: Ontology) -> Iterator[Finding]:
    """E007: one term (a name or discouraged term) used by two or more concepts."""
    owners: dict[str, dict[str, str]] = defaultdict(dict)  # normalised term -> {concept id: term as written}
    for concept in ontology.concepts.values():
        for term in own_terms(concept):
            owners[normalise(term)].setdefault(concept.id, term)
    for _, by_concept in sorted(owners.items()):
        if len(by_concept) < 2:
            continue
        for concept_id, term in sorted(by_concept.items()):
            others = ", ".join(f"'{other}'" for other in sorted(by_concept) if other != concept_id)
            yield finding(
                "E007",
                concept_id,
                f"The term '{term}' also belongs to {others}: one word with two meanings. Give the concepts "
                "distinct names, or merge them if they really are the same concept.",
            )


def _texts(concept: Concept) -> Iterable[tuple[str, str]]:
    """The prose fields where a concept's text names other concepts: (field, text)."""
    if concept.definition:
        yield "definition", concept.definition
    for field, values in (
        ("rule", concept.rules),
        ("example", concept.examples),
        ("non-example", concept.non_examples),
    ):
        for value in values:
            yield field, value


def _discouraged_in_use(ontology: Ontology) -> Iterator[Finding]:
    """W109: a definition, rule or example uses another concept's discouraged term."""
    discouraged = [
        (term.term, owner)
        for owner in ontology.concepts.values()
        for term in owner.discouraged_terms
        if term.term.strip()
    ]
    for concept in ontology.concepts.values():
        reported: set[str] = set()
        for field, text in _texts(concept):
            for term, owner in discouraged:
                if owner.id == concept.id or normalise(term) in reported or not mentions(text, term):
                    continue
                reported.add(normalise(term))
                yield finding(
                    "W109",
                    concept.id,
                    f"The {field} uses '{term}', a discouraged term for '{owner.id}'. "
                    f"Use its canonical name, '{owner.name}', instead.",
                )


def _definition(concept: Concept, min_words: int) -> Iterator[Finding]:
    """E008 empty while defined; W101 too short; W102 circular; W103 defined by its implementation."""
    text = concept.definition
    if not text:
        if concept.status == "defined":
            yield finding(
                "E008",
                concept.id,
                f"'{concept.id}' is defined but has no definition. A human writes the definition; until then "
                "set status back to proposed.",
            )
        return

    words = len(text.split())
    if words < min_words:
        yield finding(
            "W101",
            concept.id,
            f"The definition has {words} word{'s' if words != 1 else ''}; at least {min_words} are expected "
            "(min_definition_words). Say what the concept is and what sets it apart.",
        )

    head = first_sentence(text)
    circular = next((term for term in own_terms(concept) if mentions(head, term)), None)
    if circular is not None:
        yield finding(
            "W102",
            concept.id,
            f"The definition is circular: its first sentence uses '{circular}', the term being defined. "
            "Define it with other words, starting from a broader concept and what sets this one apart.",
        )

    for code_term in _code_terms(concept):
        if mentions(text, code_term):
            yield finding(
                "W103",
                concept.id,
                f"The definition mentions '{code_term}' from implemented_in, so it describes the code rather "
                "than the domain. Say what the concept means; implemented_in already records where it lives.",
            )
            break


_CODE_LIKE = re.compile(r"[_./\d]|[a-z][A-Z]")


def _code_terms(concept: Concept) -> list[str]:
    """The identifiers an implementation is known by: its path, file name, file stem and symbol.

    Only terms that look like code count (an underscore, dot, slash, digit or camelCase), so
    a symbol or file named with a plain word such as `region` or `orders` never flags prose.
    """
    terms: list[str] = []
    for impl in concept.implemented_in:
        path = PurePosixPath(impl.path)
        terms += [impl.path, path.name, path.stem]
        if impl.symbol:
            terms.append(impl.symbol)
    return list(dict.fromkeys(t for t in terms if t and _CODE_LIKE.search(t)))


def _commitment(concept: Concept, incoming: set[str]) -> Iterator[Finding]:
    """I201: an isolated concept nothing uses. I202: deprecated without replaced_by.

    A concept that other concepts point at is connected, so incoming relations count.
    Deprecated concepts are not asked whether they are needed: I202 covers them.
    """
    if concept.status == "deprecated":
        if concept.replaced_by is None:
            yield finding(
                "I202",
                concept.id,
                f"'{concept.id}' is deprecated without replaced_by. If it was renamed or merged, set replaced_by "
                "so readers and the explorer can follow it.",
            )
        return
    if not concept.relations and not concept.implemented_in and concept.id not in incoming:
        yield finding(
            "I201",
            concept.id,
            f"'{concept.id}' has no relations and no implemented_in. Is it needed? Relate it to the "
            "concepts it depends on, or record where it lives in the code.",
        )
