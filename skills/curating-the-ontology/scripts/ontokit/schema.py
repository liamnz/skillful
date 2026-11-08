"""JSON Schema validation of concept records and the manifest."""

from __future__ import annotations

import json
from functools import cache
from typing import Any, Literal

from jsonschema import Draft202012Validator

from . import ASSETS_DIR

RecordType = Literal["concept", "manifest"]


@cache
def _validator(record_type: RecordType) -> Draft202012Validator:
    path = ASSETS_DIR / "schemas" / f"{record_type}.schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _location(path: list[Any]) -> str:
    if not path:
        return "top level"
    out = ""
    for part in path:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out


def schema_errors(record_type: RecordType, data: Any) -> list[str]:
    """Human-readable schema violations, sorted, each prefixed with where it occurs."""
    errors = _validator(record_type).iter_errors(data)
    return sorted(f"{_location(list(e.absolute_path))}: {e.message}" for e in errors)
