"""Loading an ontology from disk into an immutable model.

Loading reports the structural findings (E001 parse, E002 schema, E003 identity) and
leaves bad records out of the model, so later checks only ever see valid records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from . import ASSETS_DIR
from .findings import Finding
from .schema import schema_errors

MANIFEST_FILE = "ontology.yaml"
CONCEPTS_DIR = "concepts"


class OntologyNotFound(Exception):
    """The ontology root or its manifest does not exist."""


@dataclass(frozen=True)
class Relation:
    type: str
    target: str
    cardinality: str | None = None


@dataclass(frozen=True)
class Implementation:
    path: str
    symbol: str | None = None
    reviewed_at: str | None = None


@dataclass(frozen=True)
class DiscouragedTerm:
    term: str
    note: str | None = None


@dataclass(frozen=True)
class Proposal:
    rationale: str | None = None
    suggested_definition: str | None = None


@dataclass(frozen=True)
class Concept:
    id: str
    name: str
    kind: str
    status: str
    source: Path
    definition: str = ""
    discouraged_terms: tuple[DiscouragedTerm, ...] = ()
    examples: tuple[str, ...] = ()
    non_examples: tuple[str, ...] = ()
    rules: tuple[str, ...] = ()
    relations: tuple[Relation, ...] = ()
    implemented_in: tuple[Implementation, ...] = ()
    open_questions: tuple[str, ...] = ()
    proposal: Proposal | None = None
    replaced_by: str | None = None


@dataclass(frozen=True)
class Settings:
    stale_proposal_days: int = 30
    min_definition_words: int = 8
    drift_context_lines: int = 3


@dataclass(frozen=True)
class Manifest:
    schema_version: int
    name: str
    source: Path
    description: str = ""
    kind_extensions: dict[str, dict[str, Any]] = field(default_factory=dict)
    relation_extensions: dict[str, dict[str, Any]] = field(default_factory=dict)
    settings: Settings = field(default_factory=Settings)


@dataclass(frozen=True)
class CoreVocabulary:
    kinds: dict[str, dict[str, Any]]
    relation_types: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class Ontology:
    root: Path
    core: CoreVocabulary
    manifest: Manifest | None  # None when the manifest itself is invalid
    concepts: dict[str, Concept]  # sorted by id

    @property
    def settings(self) -> Settings:
        return self.manifest.settings if self.manifest else Settings()


@cache
def core_vocabulary() -> CoreVocabulary:
    data = yaml.safe_load((ASSETS_DIR / "schemas" / "core-vocabulary.yaml").read_text(encoding="utf-8"))
    return CoreVocabulary(kinds=data["kinds"], relation_types=data["relation_types"])


def display_path(path: Path) -> str:
    """A path for messages: relative to the working directory when possible, always with '/'."""
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _parse_yaml(path: Path, concept: str | None) -> tuple[Any, list[Finding]]:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8-sig")), []
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f" (line {mark.line + 1}, column {mark.column + 1})" if mark else ""
        problem = getattr(exc, "problem", None) or str(exc)
        message = f"{display_path(path)}: YAML does not parse{where}: {problem}. Fix the syntax and re-run."
        return None, [Finding("E001", "error", concept, None, message)]
    except UnicodeDecodeError as exc:
        message = f"{display_path(path)}: file is not valid UTF-8 ({exc.reason}). Re-save it as UTF-8."
        return None, [Finding("E001", "error", concept, None, message)]


def _schema_findings(path: Path, record_type: str, data: Any, concept: str | None) -> list[Finding]:
    return [
        Finding("E002", "error", concept, None, f"{display_path(path)}: {error}")
        for error in schema_errors(record_type, data)  # type: ignore[arg-type]
    ]


def _load_manifest(path: Path) -> tuple[Manifest | None, list[Finding]]:
    data, findings = _parse_yaml(path, None)
    if findings:
        return None, findings
    findings = _schema_findings(path, "manifest", data, None)
    if findings:
        return None, findings
    extensions = data.get("extensions") or {}
    return (
        Manifest(
            schema_version=data["schema_version"],
            name=data["name"],
            source=path,
            description=data.get("description", ""),
            kind_extensions=dict(sorted((extensions.get("kinds") or {}).items())),
            relation_extensions=dict(sorted((extensions.get("relation_types") or {}).items())),
            settings=Settings(**(data.get("settings") or {})),
        ),
        [],
    )


def _concept_from(data: dict[str, Any], path: Path) -> Concept:
    proposal = data.get("proposal")
    return Concept(
        id=data["id"],
        name=data["name"],
        kind=data["kind"],
        status=data["status"],
        source=path,
        definition=(data.get("definition") or "").strip(),
        discouraged_terms=tuple(DiscouragedTerm(**t) for t in data.get("discouraged_terms") or ()),
        examples=tuple(data.get("examples") or ()),
        non_examples=tuple(data.get("non_examples") or ()),
        rules=tuple(data.get("rules") or ()),
        relations=tuple(Relation(**r) for r in data.get("relations") or ()),
        implemented_in=tuple(Implementation(**i) for i in data.get("implemented_in") or ()),
        open_questions=tuple(data.get("open_questions") or ()),
        proposal=Proposal(**proposal) if proposal else None,
        replaced_by=data.get("replaced_by"),
    )


def load(root: Path) -> tuple[Ontology, list[Finding]]:
    """Load the ontology at `root`. Raises OntologyNotFound if there is no manifest."""
    manifest_path = root / MANIFEST_FILE
    if not manifest_path.is_file():
        raise OntologyNotFound(
            f"No ontology found at {display_path(root)} (missing {MANIFEST_FILE}). "
            "Run 'onto.py init' to create one, or pass --root."
        )

    manifest, findings = _load_manifest(manifest_path)

    files = sorted((root / CONCEPTS_DIR).glob("*.yaml"))
    stems = {f.stem for f in files}
    concepts: dict[str, Concept] = {}
    for path in files:
        stem = path.stem
        data, parse_findings = _parse_yaml(path, stem)
        if parse_findings:
            findings += parse_findings
            continue
        schema_findings = _schema_findings(path, "concept", data, stem)
        if schema_findings:
            findings += schema_findings
            continue
        if data["id"] != stem:
            clash = ""
            if data["id"] in stems:
                clash = f" This is a duplicate id: concepts/{data['id']}.yaml already uses it."
            findings.append(
                Finding(
                    "E003",
                    "error",
                    stem,
                    None,
                    f"{display_path(path)}: id '{data['id']}' does not match the filename '{stem}'.{clash} "
                    "Rename the file or fix the id so they are equal.",
                )
            )
            continue
        concepts[stem] = _concept_from(data, path)

    # Sort by id, not filename: "customer-region.yaml" sorts before "customer.yaml".
    concepts = dict(sorted(concepts.items()))
    return Ontology(root=root, core=core_vocabulary(), manifest=manifest, concepts=concepts), findings
