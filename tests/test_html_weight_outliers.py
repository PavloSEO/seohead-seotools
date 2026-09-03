"""LARGE_HTML must not call an ordinary page an outlier on a templated site.

A Tukey fence measures distance in units of spread. When every page renders the
same shell the interquartile range is zero, the fence collapses onto p75, and
every page above the median is "an outlier" — which is most of the site.
"""

from __future__ import annotations

import csv

from seohead.sf.config import load_config
from seohead.sf.core.context import AuditContext
from seohead.sf.core.heuristics import check_html_weight
from seohead.sf.core.loader import load_exports


def _flagged(tmp_path, sizes) -> set[str]:
    path = tmp_path / "internal_all.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["Address", "Content Type", "Status Code", "Indexability", "Size (bytes)", "Word Count"]
        )
        for index, size in enumerate(sizes):
            writer.writerow(
                [f"https://example.com/p{index}", "text/html", "200", "Indexable", size, 500]
            )
    ctx = AuditContext(load_exports(str(tmp_path)), load_config(None))
    check_html_weight(ctx)
    return {issue.target_url for issue in ctx.issues if issue.check == "LARGE_HTML"}


def test_zero_spread_does_not_manufacture_outliers(tmp_path):
    # 20 identical pages and one 0.2% larger: nothing here is an outlier.
    assert _flagged(tmp_path, [50_000] * 20 + [50_100]) == set()


def test_near_zero_spread_does_not_manufacture_outliers(tmp_path):
    # A few bytes of variation is still one value at the resolution that matters.
    sizes = [50_000 + (index % 5) * 10 for index in range(20)] + [51_000]
    assert _flagged(tmp_path, sizes) == set()


def test_a_genuinely_heavy_page_is_still_flagged(tmp_path):
    # Four times the median trips the multiple-of-median rule with no spread at all.
    flagged = _flagged(tmp_path, [50_000] * 20 + [200_000])
    assert flagged == {"https://example.com/p20"}


def test_the_absolute_threshold_still_applies(tmp_path):
    # 200 KB is the absolute ceiling; a uniform site of 300 KB pages is all heavy.
    assert len(_flagged(tmp_path, [300_000] * 5)) == 5


def test_the_fence_still_works_on_a_spread_distribution(tmp_path):
    # Real spread: the fence is meaningful again and catches the tail.
    sizes = [10_000, 20_000, 30_000, 40_000, 50_000, 60_000, 70_000, 300_000]
    assert "https://example.com/p7" in _flagged(tmp_path, sizes)
