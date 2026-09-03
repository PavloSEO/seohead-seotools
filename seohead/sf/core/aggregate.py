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


# Crawling far fewer URLs than the sitemap declares is normal — a deliberate
# sample, a URL limit — so it marks the run partial rather than invalid. Scoring
# a fraction of a site as if it were the whole one is still worth flagging.
PARTIAL_CRAWL_RATIO = 0.2

# Below this share of the registry the score stops meaning anything: a source
# serving a fifth of the checks would grade a site on almost no evidence.
MIN_COVERAGE_TO_SCORE = 0.5


def _crawl_validity(
    n_pages: int, by_check: dict[str, int], urls_crawled: int
) -> tuple[bool, str | None]:
    """Decide whether the run produced a corpus worth scoring.

    A score of 100 next to a critical NO_RESPONSE is a false green: the run
    proved nothing, and that number is the one that reaches a client report.
    """
    if urls_crawled <= 0:
        return False, "no URLs were crawled"
    if n_pages <= 0:
        reason = "no HTML pages were crawled"
        if by_check.get("NO_RESPONSE"):
            reason = "the crawl got no response from the site"
        return False, reason
    return True, None


def _health_score(
    by_severity: dict[str, int], n_pages: int, weights: dict[str, float]
) -> int | None:
    """Score the crawl, or return ``None`` when there is nothing to score.

    Returning 100 for an empty corpus was arithmetically defensible and
    completely misleading: it is the one place the toolkit rendered "no data"
    as "no problems".
    """
    if n_pages <= 0:
        return None
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

    urls_crawled = len(ctx.pages)
    crawl_valid, invalid_reason = _crawl_validity(n_pages, dict(by_check), urls_crawled)
    run["crawl_valid"] = crawl_valid
    run["crawl_invalid_reason"] = invalid_reason
    if not crawl_valid:
        summary["health_score"] = None
        summary["health_score_reason"] = invalid_reason

    # A score built from half the checks is not comparable to one built from all
    # of them, and the difference is invisible in the number. Fewer checks means
    # less penalty means a HIGHER score, so silence here rewards missing data.
    from seohead.sf.core.registry import CHECKS

    checks_total = len(CHECKS)
    checks_skipped = len({s.id for s in ctx.skipped})
    checks_available = checks_total - checks_skipped
    # "Silent" checks neither produced an issue nor declared a skip. Some are
    # genuinely clean; some had no evidence and said nothing. Today those two are
    # indistinguishable, and naming the population is how the gap stops being
    # invisible — every declaration added moves a check out of this bucket.
    fired_checks = {i.check for i in issues}
    declared = {s.id for s in ctx.skipped}
    summary["check_coverage"] = {
        "checks_total": checks_total,
        "checks_fired": len(fired_checks),
        "checks_skipped": checks_skipped,
        "checks_silent": len(set(CHECKS) - fired_checks - declared),
        "coverage": round(checks_available / checks_total, 3) if checks_total else None,
    }
    # Below this, the number stops meaning anything: a source serving a fifth of
    # the registry would score a site on almost no evidence. Suppressing is the
    # same discipline as everywhere else — better a stated absence than a
    # confident wrong number. Note the score is deliberately NOT rescaled by
    # coverage: estimating what the checks that never ran would have found is
    # invention, so comparability is refused instead of faked.
    coverage_ratio = summary["check_coverage"]["coverage"] or 0.0
    if coverage_ratio < MIN_COVERAGE_TO_SCORE and summary["health_score"] is not None:
        summary["health_score"] = None
        summary["health_score_reason"] = (
            f"only {checks_available} of {checks_total} checks could run "
            f"({coverage_ratio:.0%} coverage); too little evidence to score"
        )

    if checks_skipped:
        summary["health_score_basis"] = (
            f"{checks_available} of {checks_total} checks could run; the score is not "
            "comparable to a run with full evidence"
        )

    # A crawl far below the declared sitemap still scores, but says so: the
    # score describes what was crawled, not the site.
    urls_in_sitemap = int((sitemap_summary or {}).get("urls_in_sitemap") or 0)
    partial = bool(
        urls_in_sitemap and crawl_valid and urls_crawled < urls_in_sitemap * PARTIAL_CRAWL_RATIO
    )
    run["crawl_partial"] = partial
    if partial:
        summary["health_score_scope"] = (
            f"{urls_crawled} of {urls_in_sitemap} sitemap URLs crawled — "
            "the score describes the crawled subset, not the whole site"
        )
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
