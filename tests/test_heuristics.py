"""Heuristics beyond SF: HTML weight outliers and derived metrics."""

from __future__ import annotations

import csv

from seohead.sf.core import heuristics
from seohead.sf.core.audit import run_audit
from tests.conftest import issues_of

_TEMPLATE_COLS = [
    "Address",
    "Content Type",
    "Status Code",
    "Indexability",
    "Title 1",
    "Meta Description 1",
    "H1-1",
    "Canonical Link Element 1",
    "Size (bytes)",
    "Word Count",
    "Text Ratio",
]


def _templated_title_issues(tmp_path, titles):
    d = tmp_path / "exports"
    d.mkdir()
    with open(d / "internal_all.csv", "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(_TEMPLATE_COLS)
        for index, title in enumerate(titles):
            url = f"https://example.com/p{index}"
            writer.writerow(
                [url, "text/html", 200, "Indexable", title, "d" * 80, "Heading", url, 1000, 500, 20]
            )
    res = run_audit(input_mode="parse-exports", exports_dir=str(d), log=lambda m: None)
    return [i.details for i in res.issues if i.check == "TITLE_TEMPLATED"]


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


def test_title_templated_detects_shared_prefix(tmp_path):
    """#206: only counting suffixes missed a whole advertised half of the heuristic."""
    issues = _templated_title_issues(tmp_path, [f"SEOHEAD — page {i}" for i in range(5)])
    assert len(issues) == 1
    assert issues[0]["direction"] == "prefix"
    assert issues[0]["token"] == "SEOHEAD"


def test_title_templated_still_detects_shared_suffix(tmp_path):
    issues = _templated_title_issues(tmp_path, [f"Page {i} — SEOHEAD" for i in range(5)])
    assert len(issues) == 1
    assert issues[0]["direction"] == "suffix"
    assert issues[0]["token"] == "SEOHEAD"


def test_title_templated_silent_without_a_separator_or_majority(tmp_path):
    issues = _templated_title_issues(
        tmp_path,
        [
            "Industrial Pumps for Sale",
            "Replacement Seals and Gaskets",
            "Water Treatment Systems",
            "Valve Actuators Overview",
            "Flow Meters and Sensors",
        ],
    )
    assert issues == []


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
