"""Freshness of the built explorer: the input hash and W108.

The hash covers the *parsed* records plus the skill version, not raw bytes, so
line endings (e.g. a Windows checkout with core.autocrlf), comments and
formatting never make a build look stale. A file that does not parse is hashed
by its text with normalised line endings, so fixing it still counts as a change.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

from . import skill_version
from .context import Context
from .findings import Finding
from .io import CONCEPTS_DIR, MANIFEST_FILE, Ontology, display_path

OUTPUT_FILE = "index.html"
HASH_META = "ontology-input-hash"
_HASH_PATTERN = re.compile(r'<meta name="' + HASH_META + r'" content="([^"]+)">')


def _normalised_text(path: Path) -> str:
    text = path.read_bytes().decode("utf-8-sig", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _record(path: Path) -> Any:
    text = _normalised_text(path)
    try:
        value = yaml.safe_load(text)
        json.dumps(value, sort_keys=True, default=str)  # e.g. mixed-type keys cannot be canonicalised
    except (yaml.YAMLError, TypeError):
        return {"unparsed": text}
    return value


def _record_files(root: Path) -> Iterator[Path]:
    manifest = root / MANIFEST_FILE
    if manifest.is_file():
        yield manifest
    yield from sorted((root / CONCEPTS_DIR).glob("*.yaml"))


def input_hash(root: Path) -> str:
    """SHA-256 of the canonical JSON of every parsed record plus the skill version."""
    payload = {
        "skillVersion": skill_version(),
        "records": {path.relative_to(root).as_posix(): _record(path) for path in _record_files(root)},
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def hash_meta(value: str) -> str:
    """The <meta> element that carries the input hash in the built page."""
    return f'<meta name="{HASH_META}" content="{value}">'


def built_hash(output: Path) -> str | None:
    """The input hash recorded in a built page, or None if it is missing or unreadable."""
    if not output.is_file():
        return None
    match = _HASH_PATTERN.search(output.read_text(encoding="utf-8", errors="replace"))
    return match.group(1) if match else None


def is_fresh(root: Path) -> bool:
    return built_hash(root / OUTPUT_FILE) == input_hash(root)


def check_staleness(ontology: Ontology, ctx: Context) -> Iterator[Finding]:
    """W108: index.html exists but was built from different records (or by another skill version)."""
    output = ontology.root / OUTPUT_FILE
    if not output.exists():
        ctx.note(f"{display_path(output)} has not been built yet. Run 'onto.py build' and commit it.")
        return
    if built_hash(output) != input_hash(ontology.root):
        yield Finding(
            "W108",
            "warn",
            None,
            None,
            f"{display_path(output)} is stale: the records changed since it was built. "
            "Run 'onto.py build' and commit the result.",
        )
