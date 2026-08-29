"""Issue aggregation: stable ids, dedup, page back-links and the summary block."""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any

from .context import AuditContext
from .models import AuditResult, Issue


def _fingerprint(issue: Issue) -> str:
    """Return a deterministic hash for diffing audit runs.

    Keyed on (check, target_url, status) only — NOT on the locations list, which
    is capped/ordered and would make the fingerprint unstable across runs.
    """
    basis = "|".join([issue.check, str(issue.target_url), str(issue.status_code)])
    return hashlib.sha1(basis.encode("utf-8"), usedforsecurity=False).hexdigest()[:12]


def _dedupe(issues: list[Issue]) -> list[Issue]:
    seen: dict[tuple[str, str | None], Issue] = {}
    out: list[Issue] = []
    for issue in issues:
        key = (issue.check, issue.target_url)
        if key in seen and issue.target_url is not None:
            # merge locations into the first occurrence rather than duplicate
            existing = seen[key]
            existing.locations.extend(issue.locations)
            unique_sources = {
                loc.get("source_url") for loc in existing.locations if loc.get("source_url")
            }
            # never undercount: locations may be capped, so keep the largest signal
            existing.occurrences_count = max(
                len(unique_sources), existing.occurrences_count, issue.occurrences_count
            )
            continue
        seen[key] = issue
        out.append(issue)
    return out


def _health_score(by_severity: dict[str, int], n_pages: int, weights: dict[str, float]) -> int:
    if n_pages <= 0:
        return 100
    penalty = sum(by_severity.get(sev, 0) * w for sev, w in weights.items())
    score = 100 - (penalty / n_pages) * 10
    return max(0, min(100, round(score)))


def aggregate(
    ctx: AuditContext,
    run: dict[str, Any],
    size_stats: dict[str, Any],
    sitemap_summary: dict[str, Any],
) -> AuditResult:
    issues = _dedupe(ctx.issues)

    # assign ordered ids + fingerprints (sorted for determinism)
    sev_rank = {"critical": 0, "warning": 1, "notice": 2}
    issues.sort(key=lambda i: (sev_rank.get(i.severity, 3), i.check, str(i.target_url)))
    for n, issue in enumerate(issues, start=1):
        issue.id = f"ISSUE-{n:06d}"
        issue.fingerprint = _fingerprint(issue)

    # back-link issues onto pages
    for issue in issues:
        page = ctx.page_by_url.get(issue.target_url) if issue.target_url else None
        if page is not None:
            if issue.check not in page.issues:
                page.issues.append(issue.check)
            page.issue_ids.append(issue.id)

    # strip private record from page metrics before serialization
    for page in ctx.pages:
        page.metrics.pop("_record", None)

    by_severity = Counter(i.severity for i in issues)
    by_check = Counter(i.check for i in issues)
    n_pages = len(ctx.html_pages())
    weights = ctx.config.get("scoring", {}).get("weights", {})

    summary: dict[str, Any] = {
        "totals": {
            "urls_crawled": len(ctx.pages),
            "html_pages": n_pages,
            "html_indexable": len(ctx.indexable_html_pages()),
            "issues_total": len(issues),
            "groups_total": len(ctx.groups),
        },
        "by_severity": {
            "critical": by_severity.get("critical", 0),
            "warning": by_severity.get("warning", 0),
            "notice": by_severity.get("notice", 0),
        },
        "by_check": dict(sorted(by_check.items(), key=lambda kv: (-kv[1], kv[0]))),
        "health_score": _health_score(by_severity, n_pages, weights),
    }
    if size_stats:
        summary["size_stats_bytes"] = {k: int(v) for k, v in size_stats.items() if k != "iqr"}
    if sitemap_summary:
        summary["sitemap"] = sitemap_summary

    # cap pages in JSON if configured
    max_pages = ctx.config.get("output", {}).get("max_pages_in_json", 100000)
    pages = ctx.pages[:max_pages]

    # A check that fired from one source isn't "skipped" just because another
    # source for it was absent (e.g. BROKEN_EXTERNAL_LINK from 4xx but not 5xx).
    fired = {i.check for i in issues}
    skipped = [s for s in ctx.skipped if s.id not in fired]

    return AuditResult(
        run=run,
        summary=summary,
        issues=issues,
        pages=pages,
        groups=ctx.groups,
        skipped=skipped,
    )
