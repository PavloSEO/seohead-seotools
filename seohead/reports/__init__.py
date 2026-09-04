"""Build Excel, Word, CSV, Markdown, or JSON reports from one audit document.

This package is the formatting boundary. The four human-facing writers
(``xlsx``, ``docx``, ``csv``, ``md``) only ever read one shape: flat
``findings``/``pages`` records, the ``seohead.site-audit/1`` contract. A
Screaming Frog audit (``sf run``'s ``audit.json`` — findings under ``issues``,
page facts nested under ``pages[].metrics``) is a second, equally real input;
:func:`_normalize_sf_audit` reshapes it into the same flat contract once, here,
so no writer has to know two schemas. ``json`` is the exception: it passes the
original document through untouched, on either contract, because it is not
reinterpreting the data, only relaying it.

A document that matches neither contract is refused rather than rendered: see
:func:`_detect_kind`. Report generators do not calculate metrics and do not
make network requests: if a value was not captured in the audit JSON, it must
remain absent rather than being invented during rendering.

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


def _detect_kind(document: dict[str, Any]) -> str | None:
    """Identify which of the two audit contracts ``document`` matches.

    ``findings`` (even empty) is the signature of ``seohead.site-audit/1``,
    written by :mod:`seohead.audit.site` and by every fixture in this
    package's own tests. ``issues`` + ``pages`` with no ``findings`` is the
    signature of an SF Analyzer ``audit.json`` (:mod:`seohead.sf.core.models`).
    Neither present means this is not a document either side of this package
    ever produces, and it must be refused rather than rendered as an empty,
    confident report (#151).
    """
    if document.get("findings") is not None:
        return "site-audit"
    if isinstance(document.get("issues"), list) and isinstance(document.get("pages"), list):
        return "sf-audit"
    return None


def _normalize_sf_audit(document: dict[str, Any]) -> dict[str, Any]:
    """Reshape an SF Analyzer ``audit.json`` into the flat site-audit contract.

    Every field copied here is real evidence already present in ``document``;
    none is computed or guessed, matching the module contract above.
    """
    run = document.get("run") or {}
    summary = document.get("summary") or {}
    totals = summary.get("totals") or {}
    by_severity = summary.get("by_severity") or {}

    findings = [
        {
            "severity": issue.get("severity"),
            "source": issue.get("source", ""),
            "url": issue.get("target_url") or "",
            "text": issue.get("message", ""),
        }
        for issue in document.get("issues") or []
    ]

    pages = []
    for page in document.get("pages") or []:
        metrics = page.get("metrics") or {}
        h1 = metrics.get("h1")
        pages.append(
            {
                "url": page.get("url", ""),
                "status": page.get("status_code"),
                "title": metrics.get("title") or "",
                "title_length": metrics.get("title_length") or "",
                "description_length": metrics.get("desc_length") or "",
                "h1": (h1[0] if isinstance(h1, list) and h1 else h1) or "",
                "canonical": metrics.get("canonical") or "",
                "words": metrics.get("word_count") or 0,
                # Schema.org and social-tag evidence live in the issue stream
                # for this contract, not in a per-page metric column; left
                # absent here rather than invented.
                "schema_types": "",
                "schema_errors": "",
                "social_missing": "",
            }
        )

    tools_failed = [
        {"tool": item.get("id"), "error": item.get("reason")}
        for item in run.get("checks_skipped") or []
    ]
    severity_note = next(
        (
            summary.get(key)
            for key in ("health_score_reason", "health_score_basis", "health_score_scope")
            if summary.get(key)
        ),
        None,
    )

    return {
        "domain": run.get("project") or "",
        "url": run.get("source") or (pages[0]["url"] if pages else ""),
        "generated_at": run.get("generated_at", ""),
        "findings": findings,
        "pages": pages,
        "summary": {
            "pages_checked": totals.get("urls_crawled", len(pages)),
            "findings_total": totals.get("issues_total", len(findings)),
            "findings_by_severity": {
                "critical": by_severity.get("critical", 0),
                "warning": by_severity.get("warning", 0),
                "notice": by_severity.get("notice", 0),
            },
            # The real names of the checks that actually fired -- not a count
            # invented to fill the column, and not the tool names of the
            # unrelated site-audit contract this summary shape started life as.
            "tools_run": list((summary.get("by_check") or {}).keys()),
            "tools_failed": tools_failed,
            "severity_note": severity_note,
        },
    }


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
    if not isinstance(document, dict):
        return {
            "ok": False,
            "error": f"audit document must be a JSON object, got {type(document).__name__}",
        }

    kind = _detect_kind(document)
    if kind is None:
        return {
            "ok": False,
            "error": (
                "audit document schema not recognized: expected 'findings' "
                "(seohead.site-audit/1) or 'issues'+'pages' (SF Analyzer audit.json); "
                f"got top-level keys {sorted(document.keys())!r}"
            ),
        }
    # The four human-facing writers only ever read the flat site-audit shape;
    # ``json`` relays the original document, on either contract, untouched.
    rendered = document if kind == "site-audit" else _normalize_sf_audit(document)

    target = pathlib.Path(path or f"audit-{rendered.get('domain', 'site')}.{fmt}")
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        if fmt == "json":
            target.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        elif fmt == "xlsx":
            from seohead.reports import xlsx

            xlsx.write(rendered, target)
        elif fmt == "docx":
            from seohead.reports import docx

            docx.write(rendered, target)
        elif fmt == "csv":
            from seohead.reports import csvfile

            csvfile.write(rendered, target)
        else:
            from seohead.reports import md

            md.write(rendered, target)
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
        "findings": len(rendered.get("findings") or []),
        "pages": len(rendered.get("pages") or []),
    }
