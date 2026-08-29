"""Write the ``audit.json`` machine-readable contract."""

from __future__ import annotations

import json
import os
from typing import Any

from ..core.models import AuditResult


def to_dict(result: AuditResult) -> dict[str, Any]:
    return result.to_json()


def write_json(result: AuditResult, path: str) -> str:
    data = to_dict(result)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)  # atomic: never leave a half-written audit.json
    return path


def load_schema() -> dict[str, Any]:
    """Load the bundled JSON Schema, working for both editable and wheel installs."""
    from importlib.resources import files

    text = files("seohead.sf.schema").joinpath("audit.schema.json").read_text("utf-8")
    return json.loads(text)


def validate(result: AuditResult) -> list[str]:
    """Validate against the bundled JSON Schema; return a list of errors."""
    import jsonschema  # optional dependency, imported lazily

    validator = jsonschema.Draft202012Validator(load_schema())
    return [e.message for e in validator.iter_errors(to_dict(result))]
