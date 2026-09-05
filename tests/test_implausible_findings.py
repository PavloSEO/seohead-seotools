"""A check that describes most of a site is a claim to look at before believing.

Issue #98: three defects found on live sites (#94, #95, #96) all passed their unit
tests and all failed on real HTML, and each was visible in the same way — the
check accounted for an implausible share of the report. #94 fired 392 times
across 124 of 167 pages. Nobody noticed until a person read the output.

The measure is deliberately not a failure. A site really can have no meta
description anywhere, and saying so on every page is correct. It names what a
reviewer must check, which is the one line that would have caught all three.
"""

from __future__ import annotations

from seohead.sf.core.aggregate import IMPLAUSIBLE_SHARE, _implausible_checks
from seohead.sf.core.models import Issue


def _issue(check: str, url: str) -> Issue:
    return Issue(check=check, severity="warning", source="s", message="m", target_url=url)


def test_a_check_covering_most_of_the_crawl_is_named():
    """The #94 shape: one check, most of the site, many occurrences per page."""
    issues = [_issue("URL_NOT_IN_SITEMAP", f"https://example.com/p{n}") for n in range(124)]
    # The same check firing repeatedly on one page must not inflate its breadth.
    issues += [_issue("URL_NOT_IN_SITEMAP", "https://example.com/p0") for _ in range(268)]

    flagged = _implausible_checks(issues, n_pages=167)

    assert [row["check"] for row in flagged] == ["URL_NOT_IN_SITEMAP"]
    assert flagged[0]["pages"] == 124
    assert flagged[0]["share"] == round(124 / 167, 3)


def test_a_check_on_a_minority_of_pages_is_not_named():
    """The ordinary case, and the one that must stay quiet: a real finding about a
    few pages is exactly what the tool is for."""
    issues = [_issue("BROKEN_INTERNAL_LINK", f"https://example.com/p{n}") for n in range(3)]

    assert _implausible_checks(issues, n_pages=100) == []


def test_the_threshold_is_a_strict_majority():
    """Exactly half is not flagged: a site split evenly between two templates is a
    real shape, not a suspicious one."""
    half = [_issue("DESC_MISSING", f"https://example.com/p{n}") for n in range(50)]
    assert _implausible_checks(half, n_pages=100) == []

    one_more = [*half, _issue("DESC_MISSING", "https://example.com/p50")]
    assert [row["check"] for row in _implausible_checks(one_more, n_pages=100)] == ["DESC_MISSING"]
    assert IMPLAUSIBLE_SHARE == 0.5


def test_breadth_is_counted_by_page_not_by_occurrence():
    """A check that fires a thousand times on one page of a thousand describes one
    page. Counting occurrences would call that a site-wide problem."""
    issues = [_issue("HREFLANG_ERROR", "https://example.com/only") for _ in range(1000)]

    assert _implausible_checks(issues, n_pages=1000) == []


def test_locations_count_toward_breadth():
    """A grouped finding carries its pages in ``locations`` rather than one
    ``target_url``; ignoring those would let the largest findings escape the check
    precisely because they are large."""
    grouped = Issue(
        check="TITLE_DUPLICATE",
        severity="warning",
        source="s",
        message="m",
        locations=[{"url": f"https://example.com/p{n}"} for n in range(9)],
    )

    flagged = _implausible_checks([grouped], n_pages=10)

    assert [row["check"] for row in flagged] == ["TITLE_DUPLICATE"]
    assert flagged[0]["pages"] == 9


def test_an_empty_crawl_reports_nothing_rather_than_dividing_by_zero():
    assert _implausible_checks([_issue("X", "https://example.com/")], n_pages=0) == []
