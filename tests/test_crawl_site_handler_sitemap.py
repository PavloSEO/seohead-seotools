"""Handler wiring for sitemap-seeded crawl mode. No network.

The spider's own BFS and ``sitemap.crawl()``'s XML parsing are already covered
elsewhere; this only proves ``handlers.crawl_site`` wires the two together and
that the reconciliation lands in ``audit.json`` under the same key the
Screaming Frog pipeline uses (``summary.sitemap``), with the SITEMAP_ORPHAN and
URL_NOT_IN_SITEMAP check ids that pipeline already defines.
"""

from __future__ import annotations

import seohead.tools.sitemap as sitemap_tool
from seohead.crawl.collect import PageRecord
from seohead.crawl.spider import LinkEdge, SpiderResult
from seohead.servers import handlers

DECLARED = [f"https://example.com/p{i}" for i in range(1, 9)] + [
    "https://example.com/p9",
    "https://example.com/p10",
]
LINKED = DECLARED[:8]
ORPHANED = DECLARED[8:]


def _fake_spider_result() -> SpiderResult:
    result = SpiderResult()
    result.pages = [PageRecord(url=u, status_code=200, content_type="text/html") for u in DECLARED]
    result.pages.append(
        PageRecord(url="https://example.com/extra", status_code=200, content_type="text/html")
    )
    # Every linked URL, plus one the sitemap never declares, is reachable by
    # following a link from the home page. The two orphans never appear here.
    result.links = [
        LinkEdge(source="https://example.com/", destination=u, anchor="", nofollow=False)
        for u in [*LINKED, "https://example.com/extra"]
    ]
    result.seed_urls = list(DECLARED)
    return result


def test_handler_reconciles_a_sitemap_seeded_crawl(monkeypatch):
    monkeypatch.setattr(
        sitemap_tool,
        "crawl",
        lambda url, concurrency=3: {"urls": [{"loc": u} for u in DECLARED]},
    )
    monkeypatch.setattr("seohead.crawl.spider.crawl_site", lambda *a, **kw: _fake_spider_result())

    out = handlers.crawl_site(url="https://example.com/", sitemap="https://example.com/sitemap.xml")

    sitemap_summary = out["summary"]["sitemap"]
    assert sitemap_summary["sitemap_url"] == "https://example.com/sitemap.xml"
    assert sorted(sitemap_summary["in_sitemap_and_linked"]) == sorted(LINKED)
    assert sorted(sitemap_summary["in_sitemap_not_linked"]) == sorted(ORPHANED)
    assert sitemap_summary["linked_not_in_sitemap"] == ["https://example.com/extra"]

    assert out["discovery"]["sitemap_url"] == "https://example.com/sitemap.xml"
    assert out["discovery"]["sitemap_seeded"] == len(DECLARED)

    # The same check ids the Screaming Frog pipeline uses for this distinction,
    # so downstream tooling reading audit.json needs only one schema.
    by_check = out["summary"]["by_check"]
    assert by_check["SITEMAP_ORPHAN"] == len(ORPHANED)
    assert by_check["URL_NOT_IN_SITEMAP"] == 1


def test_handler_without_sitemap_reports_no_sitemap_summary(monkeypatch):
    result = _fake_spider_result()
    result.seed_urls = []
    monkeypatch.setattr("seohead.crawl.spider.crawl_site", lambda *a, **kw: result)

    out = handlers.crawl_site(url="https://example.com/")

    assert "sitemap" not in out["summary"]
    assert out["discovery"]["sitemap_url"] is None
    assert out["discovery"]["sitemap_seeded"] == 0


# ── URL_NOT_IN_SITEMAP compares pages with pages (#94) ───────────────────────


def _site_with_the_four_wrong_populations() -> SpiderResult:
    """One real omission, surrounded by the four kinds of URL that are not one.

    Each of these was reported as a sitemap defect on a live site: an outbound link, a
    gallery link straight to an image file, a URL the crawl recorded a link to but never
    fetched (budget or scope), and a page the site deliberately marked noindex.
    """
    result = SpiderResult()
    result.pages = [
        PageRecord(url="https://example.com/", status_code=200, content_type="text/html"),
        PageRecord(url="https://example.com/declared", status_code=200, content_type="text/html"),
        # The one real finding: an indexable page, linked, that the sitemap forgot.
        PageRecord(url="https://example.com/undeclared", status_code=200, content_type="text/html"),
        PageRecord(
            url="https://example.com/gallery/photo.jpg", status_code=200, content_type="image/jpeg"
        ),
        PageRecord(
            url="https://example.com/private",
            status_code=200,
            content_type="text/html",
            meta_robots="noindex, follow",
        ),
        PageRecord(url="https://example.com/gone", status_code=404, content_type="text/html"),
    ]
    result.links = [
        LinkEdge(source="https://example.com/", destination=destination, anchor="", nofollow=False)
        for destination in (
            "https://example.com/declared",
            "https://example.com/undeclared",
            "https://example.com/gallery/photo.jpg",
            "https://example.com/private",
            "https://example.com/gone",
            "https://wa.me/1234567890",  # outbound
            "https://example.com/never-fetched",  # linked, outside the budget
        )
    ]
    result.seed_urls = ["https://example.com/declared"]
    return result


def test_only_a_missing_page_is_reported_not_files_hosts_or_uncrawled_urls(monkeypatch):
    monkeypatch.setattr(
        sitemap_tool,
        "crawl",
        lambda url, concurrency=3: {
            "urls": [{"loc": "https://example.com/"}, {"loc": "https://example.com/declared"}]
        },
    )
    monkeypatch.setattr(
        "seohead.crawl.spider.crawl_site", lambda *a, **kw: _site_with_the_four_wrong_populations()
    )

    out = handlers.crawl_site(url="https://example.com/", sitemap="https://example.com/sitemap.xml")
    summary = out["summary"]["sitemap"]

    assert summary["linked_not_in_sitemap"] == ["https://example.com/undeclared"]
    assert out["summary"]["by_check"].get("URL_NOT_IN_SITEMAP") == 1

    # Nothing is silently discarded: what was set aside is named.
    set_aside = set(summary["linked_not_comparable"])
    assert "https://wa.me/1234567890" in set_aside
    assert "https://example.com/gallery/photo.jpg" in set_aside
    assert "https://example.com/never-fetched" in set_aside
    assert "https://example.com/private" in set_aside
    assert "https://example.com/gone" in set_aside


def test_narrowing_the_comparable_side_does_not_invent_orphans(monkeypatch):
    """A declared URL that is noindex, or not HTML, is still reachable — so it must not
    turn into a SITEMAP_ORPHAN just because it left the URL_NOT_IN_SITEMAP population."""
    declared = ["https://example.com/private", "https://example.com/gallery/photo.jpg"]
    monkeypatch.setattr(
        sitemap_tool, "crawl", lambda url, concurrency=3: {"urls": [{"loc": u} for u in declared]}
    )
    monkeypatch.setattr(
        "seohead.crawl.spider.crawl_site", lambda *a, **kw: _site_with_the_four_wrong_populations()
    )

    out = handlers.crawl_site(url="https://example.com/", sitemap="https://example.com/sitemap.xml")

    assert out["summary"]["sitemap"]["in_sitemap_not_linked"] == []
    assert "SITEMAP_ORPHAN" not in out["summary"]["by_check"]
