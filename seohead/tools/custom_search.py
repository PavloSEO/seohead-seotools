"""A query language over a crawled corpus: presence and absence checks.

Roughly half of real audit questions are site-specific and cannot be answered
by a fixed check registry: which pages still carry the old phone number, the
staging domain, the previous analytics id; which pages have no price; which
pages carry a tracking tag and which do not. Adding a Python function per
client is not an answer — the question changes faster than a release cycle.
This module is the fixed answer: one filter shape, applied over a corpus the
caller already has.

**Absence is the valuable half, and the easy one to get wrong.** "Which pages
lack the consent banner" is not "count the pages where a search misses" —
the pages the crawl never actually saw (a timeout, a 5xx, a blocked fetch)
must be dropped from *both* the numerator and the denominator, never counted
as "missing", or a fetch failure quietly becomes evidence of an SEO defect.
Every filter therefore reports ``pages_considered`` (successfully fetched
pages only) and ``pages_excluded_fetch_failed`` beside its counts, so "not
found on 40 of 900 pages" always names its denominator.

A document is any ``{"url", "ok", ...}`` dict — the shape a crawl, ``parse``,
or a Screaming Frog export already produces. ``ok`` (default True) marks
whether the fetch succeeded; a falsy ``ok`` excludes the document entirely.
Depending on the filter's ``scope`` a document also needs:
  raw        -- ``html``: the raw response body.
  text       -- ``text``: the visible page text; derived from ``html`` with a
                script/style-stripped ``get_text()`` when omitted.
  element    -- ``html`` plus the filter's ``selector`` (a CSS selector); the
                text of every matched element, joined.
  xpath      -- ``html`` plus the filter's ``selector`` (an XPath expression);
                the string value of every matched node, joined.
``rendered`` (default False) marks whether ``html``/``text`` is the raw
response or a post-script DOM snapshot; :func:`run_search` reports which
representation each filter actually ran against, because a tag injected by
script is invisible to raw source and present in rendered text — searching
one and reporting on "the page" as if it were the other is how an audit loses
credibility.

This module is pure and performs no network access.
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

SCOPES: tuple[str, ...] = ("raw", "text", "element", "xpath")
MODES: tuple[str, ...] = ("contains", "not_contains")
KINDS: tuple[str, ...] = ("text", "regex")


def _visible_text(html: str) -> str:
    soup = BeautifulSoup(html or "", features="lxml")
    body = soup.body or soup
    for tag in body.find_all(["script", "style", "noscript", "template"]):
        tag.decompose()
    return " ".join(body.get_text(" ").split())


def _element_text(html: str, selector: str) -> str:
    soup = BeautifulSoup(html or "", features="lxml")
    try:
        matches = soup.select(selector)
    except Exception:
        return ""  # an invalid selector matches nothing rather than raising
    return " ".join(m.get_text(" ") for m in matches)


def _xpath_text(html: str, expression: str) -> str:
    from lxml import etree

    try:
        tree = etree.HTML((html or "").encode("utf-8", "ignore"))
    except Exception:
        return ""
    if tree is None:
        return ""
    try:
        result = tree.xpath(expression)
    except Exception:
        return ""  # an invalid XPath expression matches nothing rather than raising
    if isinstance(result, str):
        return result
    parts = []
    for node in result if isinstance(result, list) else [result]:
        if isinstance(node, str):
            parts.append(node)
        elif hasattr(node, "xpath"):
            parts.append(str(node.xpath("string()")))
        else:
            parts.append(str(node))
    return " ".join(parts)


def _target_text(document: dict[str, Any], scope: str, selector: str) -> str:
    """The string a filter's ``query`` is matched against, for one document."""
    html = document.get("html") or ""
    if scope == "raw":
        return html
    if scope == "text":
        text = document.get("text")
        return text if text is not None else _visible_text(html)
    if scope == "element":
        return _element_text(html, selector)
    if scope == "xpath":
        return _xpath_text(html, selector)
    raise ValueError(f"unknown scope {scope!r}; expected one of {SCOPES}")


def _matches(target: str, kind: str, query: str, case_sensitive: bool) -> bool:
    if kind == "regex":
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            return re.search(query, target, flags) is not None
        except re.error:
            return False  # an invalid pattern matches nothing rather than raising
    if not case_sensitive:
        target, query = target.lower(), query.lower()
    return query in target


def _validate_filter(
    scope: str, selector: str, kind: str, query: str, case_sensitive: bool
) -> None:
    """Reject malformed user expressions before they become absence evidence."""
    if scope == "element":
        try:
            BeautifulSoup("", features="lxml").select(selector)
        except Exception as exc:
            raise ValueError(f"invalid CSS selector {selector!r}: {exc}") from exc
    elif scope == "xpath":
        from lxml import etree

        try:
            etree.XPath(selector)
        except etree.XPathSyntaxError as exc:
            raise ValueError(f"invalid XPath expression {selector!r}: {exc}") from exc
    if kind == "regex":
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            re.compile(query, flags)
        except re.error as exc:
            raise ValueError(f"invalid regular expression {query!r}: {exc}") from exc


def _representation(documents: list[dict[str, Any]]) -> Any:
    stamps = sorted({"rendered_dom" if d.get("rendered") else "static_markup" for d in documents})
    return stamps[0] if len(stamps) == 1 else stamps


def run_filter(documents: list[dict[str, Any]], spec: dict[str, Any]) -> dict[str, Any]:
    """Apply one filter over ``documents``; see the module docstring for shapes."""
    name = spec.get("name") or spec.get("query", "")
    mode = spec.get("mode", "contains")
    kind = spec.get("kind", "text")
    scope = spec.get("scope", "text")
    query = spec.get("query", "")
    selector = spec.get("selector", "")
    case_sensitive = bool(spec.get("case_sensitive", False))

    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}; expected one of {KINDS}")
    if scope not in SCOPES:
        raise ValueError(f"unknown scope {scope!r}; expected one of {SCOPES}")
    if scope in ("element", "xpath") and not selector:
        raise ValueError(f"scope {scope!r} requires a selector")
    _validate_filter(scope, selector, kind, query, case_sensitive)

    fetched = [d for d in documents if d.get("ok", True)]
    hits: list[str] = []
    for doc in fetched:
        target = _target_text(doc, scope, selector)
        if _matches(target, kind, query, case_sensitive):
            hits.append(doc.get("url", ""))

    # "contains" reports pages carrying it; "not_contains" reports pages
    # lacking it — the absence set the module docstring is built around.
    if mode == "contains":
        matching = hits
    else:
        hit_set = set(hits)
        matching = [d.get("url", "") for d in fetched if d.get("url", "") not in hit_set]

    return {
        "name": name,
        "mode": mode,
        "kind": kind,
        "scope": scope,
        "query": query,
        "representation": _representation(fetched),
        "pages_considered": len(fetched),
        "pages_excluded_fetch_failed": len(documents) - len(fetched),
        "matching_pages": matching,
        "count": len(matching),
        "fraction": round(len(matching) / len(fetched), 4) if fetched else 0.0,
    }


def run_search(documents: list[dict[str, Any]], filters: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply every filter in ``filters`` over ``documents``. Pure; no network access."""
    return {"ok": True, "filters": [run_filter(documents, spec) for spec in filters]}
