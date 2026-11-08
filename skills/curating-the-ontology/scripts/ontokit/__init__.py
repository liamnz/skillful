"""ontokit: the library behind onto.py.

Paths to the skill's own files are resolved from this file's location, never from
the current working directory, so the skill works wherever it is copied.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
SKILL_DIR = PACKAGE_DIR.parent.parent
ASSETS_DIR = SKILL_DIR / "assets"


@cache
def skill_version() -> str:
    """The skill's version, read from `metadata.version` in SKILL.md (single source)."""
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1] if text.startswith("---") else ""
    match = re.search(r'^\s+version:\s*"([^"]+)"', frontmatter, re.MULTILINE)
    return match.group(1) if match else "unknown"
