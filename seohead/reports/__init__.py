"""Build Excel, Word, CSV, Markdown, or JSON reports from one audit document.

This package is the formatting boundary. It accepts a
``seohead.site-audit/1`` document and writes the requested representation. Report
generators do not calculate metrics and do not make network requests: if a value
was not captured in the audit JSON, it must remain absent rather than being
invented during rendering.

Formats are separated by operational purpose, not personal preference:

``xlsx``  tables, filters, and a live chart for sorting, triage, and assigning
          individual findings to developers
``docx``  a narrative document with headings for client review and approval
``csv``   flat records for importing into a task tracker or another database
``md``    a portable report for editors, repositories, and correspondence
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

FORMATS = ("xlsx", "docx", "csv", "md", "json")

SEVERITY_TITLES = {
    "critical": "Critical",
    "warning": "Warning",
    "notice": "Notice",
}


def _load(data: Any) -> dict[str, Any]:
    """Load an audit document from a mapping or a JSON file path."""
    if isinstance(data, dict):
        return data
    path = pathlib.Path(str(data))
    if not path.exists():
        raise FileNotFoundError(f"audit file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_report(data: Any, fmt: str = "xlsx", path: str | None = None) -> dict[str, Any]:
    """Render an audit document in the requested report format.

    ``data`` is either the audit mapping itself or the path to its JSON file.
    ``path`` selects the output location; when omitted, the name is derived from
    the audited domain and the format.
    """
    fmt = (fmt or "xlsx").lower().lstrip(".")
    if fmt not in FORMATS:
        return {
            "ok": False,
            "error": f"report format {fmt!r} is not supported; "
            f"available formats: {', '.join(FORMATS)}",
        }
    try:
        document = _load(data)
    except (FileNotFoundError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}
    if not isinstance(document, dict) or not document.get("findings") is not None:
        pass  # An empty audit is valid: the report will be short but honest.

    target = pathlib.Path(path or f"audit-{document.get('domain', 'site')}.{fmt}")
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        if fmt == "json":
            target.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        elif fmt == "xlsx":
            from seohead.reports import xlsx

            xlsx.write(document, target)
        elif fmt == "docx":
            from seohead.reports import docx

            docx.write(document, target)
        elif fmt == "csv":
            from seohead.reports import csvfile

            csvfile.write(document, target)
        else:
            from seohead.reports import md

            md.write(document, target)
    except ImportError as exc:
        return {
            "ok": False,
            "error": f"dependency required for {fmt} is missing: {exc}",
            "install": "pip install 'seohead[reports]'",
        }
    # File output is an external boundary. Return the failure as structured data
    # so CLI and MCP callers receive the same non-crashing contract.
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    return {
        "ok": True,
        "format": fmt,
        "path": str(target),
        "bytes": target.stat().st_size,
        "findings": len(document.get("findings") or []),
        "pages": len(document.get("pages") or []),
    }
