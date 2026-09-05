"""Diff two audits: what changed, not just what each one found separately.

The most repeated billable question in audit work is "did the developer
actually ship the fix", and a naive diff cannot answer it. A page that stopped
matching a finding because it was fixed, and a page that stopped matching
because it was deleted from the crawl entirely, look identical if you only
compare two sets of findings — and they mean opposite things.

Page findings land in exactly one of four disjoint sets, keyed by the
finding's own fingerprint plus the URL it was found on:

    entered      the URL existed in both crawls; it did not match before, matches now
    left         the URL existed in both crawls; it matched before, does not match now
    appeared     the URL is new to this crawl, and matches now
    disappeared  the URL is gone from this crawl, and matched before

Audit-wide findings with no target URL have no page-coverage claim, so they
are kept separately under ``global.entered`` and ``global.left``.

"left" is progress. "disappeared" is not progress — the URL that was broken is
simply no longer part of what was measured, which is a different fact and must
not be reported as a fix.
"""

from __future__ import annotations

from typing import Any


class CompareError(ValueError):
    """Two audits that cannot be compared without lying about the result."""


def _key(issue: dict[str, Any]) -> tuple[str, str]:
    """(check, target_url) — the same finding on the same page, across runs.

    Not the fingerprint alone: the fingerprint already folds in target_url, so
    this is equivalent, but naming both parts keeps the four sets legible.
    """
    return (issue.get("check", ""), str(issue.get("target_url") or ""))


def _crawled_urls(audit: dict[str, Any]) -> set[str]:
    return {p["url"] for p in audit.get("pages", []) if p.get("url")}


def _by_key(audit: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {_key(issue): issue for issue in audit.get("issues", []) if issue.get("check")}


def preflight(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """Reasons a comparison would mislead, without refusing outright.

    A caller decides whether to proceed; this only says what to distrust.
    """
    warnings: list[str] = []
    for label, audit in (("before", before), ("after", after)):
        if audit.get("run", {}).get("crawl_valid") is False:
            warnings.append(f"{label} crawl is marked invalid — it measured nothing usable")
        if audit.get("run", {}).get("crawl_partial"):
            unreliable = "appeared" if label == "before" else "disappeared"
            warnings.append(
                f"{label} crawl is partial — an '{unreliable}' finding may only mean "
                "the crawl did not reach that URL, not that the page changed"
            )
    before_cfg = before.get("run", {}).get("crawl_config")
    after_cfg = after.get("run", {}).get("crawl_config")
    if before_cfg is not None and after_cfg is not None and before_cfg != after_cfg:
        changed = sorted(
            k for k in set(before_cfg) | set(after_cfg) if before_cfg.get(k) != after_cfg.get(k)
        )
        warnings.append(
            "results-affecting settings differ between the two runs, so some of the "
            f"difference may be the configuration rather than the site: {', '.join(changed)}"
        )
    return warnings


def compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Diff two audit.json documents into the four sets, per check.

    Both documents must carry ``pages`` and ``issues`` in the shape this
    toolkit produces; a document missing either is refused by name rather than
    silently treated as empty, because an empty crawl and an unreadable one
    must not look the same in the result.
    """
    for label, audit in (("before", before), ("after", after)):
        if "pages" not in audit or "issues" not in audit:
            raise CompareError(f"{label} is not an audit.json document (missing pages or issues)")

    before_urls = _crawled_urls(before)
    after_urls = _crawled_urls(after)
    before_issues = _by_key(before)
    after_issues = _by_key(after)

    entered: list[dict[str, Any]] = []
    left: list[dict[str, Any]] = []
    appeared: list[dict[str, Any]] = []
    disappeared: list[dict[str, Any]] = []
    global_entered: list[dict[str, Any]] = []
    global_left: list[dict[str, Any]] = []

    all_keys = set(before_issues) | set(after_issues)
    for key in all_keys:
        url = key[1]
        in_before = key in before_issues
        in_after = key in after_issues
        is_global = (in_before and before_issues[key].get("target_url") is None) or (
            in_after and after_issues[key].get("target_url") is None
        )
        if is_global:
            if in_after and not in_before:
                global_entered.append(dict(after_issues[key]))
            elif in_before and not in_after:
                global_left.append(dict(before_issues[key]))
            continue
        url_in_before_crawl = url in before_urls
        url_in_after_crawl = url in after_urls

        if in_before and in_after:
            continue  # unchanged: matched in both, not a difference
        if in_after and not in_before:
            record = dict(after_issues[key])
            if url_in_before_crawl:
                entered.append(record)  # existed before, is a new finding now
            else:
                appeared.append(record)  # the URL itself is new to this crawl
        elif in_before and not in_after:
            record = dict(before_issues[key])
            if url_in_after_crawl:
                left.append(record)  # still crawled, no longer matches — a fix
            else:
                disappeared.append(record)  # not in this crawl at all — unproven

    def _sort(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(items, key=lambda i: (i.get("check", ""), str(i.get("target_url") or "")))

    by_check: dict[str, dict[str, int]] = {}
    for bucket_name, bucket in (
        ("entered", entered),
        ("left", left),
        ("appeared", appeared),
        ("disappeared", disappeared),
    ):
        for item in bucket:
            row = by_check.setdefault(
                item["check"], {"entered": 0, "left": 0, "appeared": 0, "disappeared": 0}
            )
            row[bucket_name] += 1

    return {
        "schema_version": "compare.v1",
        "before": {
            "generated_at": before.get("run", {}).get("generated_at"),
            "urls_crawled": len(before_urls),
        },
        "after": {
            "generated_at": after.get("run", {}).get("generated_at"),
            "urls_crawled": len(after_urls),
        },
        "warnings": preflight(before, after),
        "summary": {
            "entered": len(entered),
            "left": len(left),
            "appeared": len(appeared),
            "disappeared": len(disappeared),
            "by_check": by_check,
        },
        "entered": _sort(entered),
        "left": _sort(left),
        "appeared": _sort(appeared),
        "disappeared": _sort(disappeared),
        "global": {
            "entered": _sort(global_entered),
            "left": _sort(global_left),
        },
    }
