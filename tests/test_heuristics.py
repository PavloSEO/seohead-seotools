"""Heuristics beyond SF: HTML weight outliers and derived metrics."""

from __future__ import annotations

from tests.conftest import issues_of


def test_large_html_outlier_flagged(result):
    issues = issues_of(result, "LARGE_HTML")
    urls = {i.target_url for i in issues}
    # 300 KB page against a ~75 KB median is the outlier
    assert "https://example.com/no-title" in urls
    issue = next(i for i in issues if i.target_url == "https://example.com/no-title")
    assert issue.details["size_bytes"] == 300000
    assert issue.details["ratio"] > 3
    assert issue.details["rank"] == 1


def test_size_stats_in_summary(result):
    stats = result.summary.get("size_stats_bytes")
    assert stats and stats["count"] >= 4
    assert stats["max"] == 300000


def test_derived_metrics_on_pages(result):
    page = next(p for p in result.pages if p.url == "https://example.com/page-b")
    assert page.metrics["bytes_per_word"] is not None
    assert page.metrics["size_vs_median_ratio"] is not None
    # private record must be stripped before serialization
    assert "_record" not in page.metrics
