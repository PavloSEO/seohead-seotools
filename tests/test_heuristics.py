"""Heuristics beyond SF: HTML weight outliers and derived metrics."""

from __future__ import annotations

from seohead.sf.core import heuristics
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


def test_dom_metrics_depth_and_nodes():
    html = "<html><body><div><p><span>hi</span></p></div></body></html>"
    depth, nodes = heuristics._dom_metrics(html)
    assert nodes == 5  # html, body, div, p, span
    assert depth == 4  # html=0 .. span=4


def test_html_index_matches_by_path_and_basename(tmp_path):
    host_dir = tmp_path / "example.com" / "blog"
    host_dir.mkdir(parents=True)
    f = host_dir / "post.html"
    f.write_text("<html></html>", encoding="utf-8")
    index = heuristics._build_html_index(str(tmp_path))
    # host+path key and basename key both resolve
    assert heuristics._match_html_file(index, "https://example.com/blog/post.html") == str(f)
    assert heuristics._match_html_file(index, "https://other/zzz/post.html") == str(f)
    assert heuristics._match_html_file(index, "https://example.com/missing.html") is None
