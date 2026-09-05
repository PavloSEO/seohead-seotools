"""run_sitemap's declared-vs-crawled reconciliation, in the shape the native
crawler's own reconcile_sitemap() also produces. Network-free: sitemap
membership comes from SF's own ``urls_in_sitemap`` export, never fetched.
"""

from __future__ import annotations

import csv

from seohead.sf.config import load_config
from seohead.sf.core.context import AuditContext
from seohead.sf.core.loader import load_exports
from seohead.sf.core.sitemap_coverage import run_sitemap


def _write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def _ctx(tmp_path, crawled_urls, sitemap_urls):
    _write_csv(
        tmp_path / "internal_all.csv",
        ["Address", "Content Type", "Status Code", "Indexability"],
        [[u, "text/html", "200", "Indexable"] for u in crawled_urls],
    )
    _write_csv(tmp_path / "urls_in_sitemap.csv", ["Address"], [[u] for u in sitemap_urls])
    return AuditContext(load_exports(str(tmp_path)), load_config(None))


def test_three_disjoint_sets_under_the_same_keys_the_native_crawler_uses(tmp_path):
    ctx = _ctx(
        tmp_path,
        crawled_urls=[
            "https://example.com/a",
            "https://example.com/b",
            "https://example.com/extra",
        ],
        sitemap_urls=[
            "https://example.com/a",
            "https://example.com/b",
            "https://example.com/orphan",
        ],
    )
    summary = run_sitemap(ctx)

    assert sorted(summary["in_sitemap_and_linked"]) == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert summary["in_sitemap_not_linked"] == ["https://example.com/orphan"]
    assert summary["linked_not_in_sitemap"] == ["https://example.com/extra"]

    # Counts stay consistent with the existing (SF-native) count fields.
    assert summary["in_sitemap_not_in_crawl"] == 1
    assert summary["in_crawl_not_in_sitemap"] == 1


def test_no_reconciliation_keys_without_a_sitemap_url_set(tmp_path):
    ctx = _ctx(tmp_path, crawled_urls=["https://example.com/a"], sitemap_urls=[])
    summary = run_sitemap(ctx)
    assert "in_sitemap_and_linked" not in summary
    assert "in_sitemap_not_linked" not in summary
    assert "linked_not_in_sitemap" not in summary


def test_a_trailing_slash_only_difference_is_not_desync(tmp_path):
    """#145: SITEMAP_DESYNC compared raw URL strings, so a canonical written without a
    trailing slash never matched the crawled page that has one -- 100% desync on a site
    that reconcile_sitemap() (the native crawl path's own comparison) reports as 0% for
    the exact same input, because that path already compares on normalize_url()'s key.
    """
    ctx = _ctx(
        tmp_path,
        crawled_urls=["https://example.com/a/"],
        sitemap_urls=["https://example.com/a"],
    )
    summary = run_sitemap(ctx)

    assert summary["in_sitemap_and_linked"] == ["https://example.com/a/"]
    assert summary["in_sitemap_not_linked"] == []
    assert summary["linked_not_in_sitemap"] == []
    assert not [issue for issue in ctx.issues if issue.check == "SITEMAP_DESYNC"], (
        "a trailing-slash-only mismatch must not read as the crawl and the sitemap "
        "disagreeing about every page"
    )
    page = ctx.pages[0]
    assert page.metrics["is_in_sitemap"] is True
