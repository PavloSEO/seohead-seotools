"""The sitemap protocol's two hard limits, and a URL declared twice.

A sitemap over 50,000 URLs or 50 MB uncompressed is not "large", it is **invalid**: a search
engine may read part of it and discard the rest, silently, with nothing the site owner can see.
Nothing in this toolkit said so until now (#124).
"""

from __future__ import annotations

from seohead.sf.core.sitemap_coverage import (
    MAX_SITEMAP_BYTES_PER_FILE,
    MAX_SITEMAP_URLS_PER_FILE,
    _check_protocol_limits,
)


class _Ctx:
    """The two methods _check_protocol_limits uses, and nothing else."""

    def __init__(self) -> None:
        self.added: list[tuple[str, str | None, dict]] = []

    def add(self, check, target_url=None, occurrences_count=None, details=None):
        self.added.append((check, target_url, details or {}))


def _fired(ctx: _Ctx, check: str) -> list[tuple[str, str | None, dict]]:
    return [row for row in ctx.added if row[0] == check]


def test_a_sitemap_over_fifty_thousand_urls_is_reported_against_that_document():
    ctx = _Ctx()
    documents = [
        {"url": "https://example.com/sitemap-1.xml", "bytes": 1000, "declared": 50_001},
        {"url": "https://example.com/sitemap-2.xml", "bytes": 1000, "declared": 50_000},
    ]
    _check_protocol_limits(ctx, documents, [], {})

    fired = _fired(ctx, "SITEMAP_TOO_MANY_URLS")
    assert len(fired) == 1, "the limit is per file, and one file is inside it"
    assert fired[0][1] == "https://example.com/sitemap-1.xml", "name the child, not the index"
    assert fired[0][2] == {"declared": 50_001, "limit": MAX_SITEMAP_URLS_PER_FILE}


def test_exactly_fifty_thousand_urls_is_allowed():
    ctx = _Ctx()
    _check_protocol_limits(
        ctx, [{"url": "https://example.com/s.xml", "bytes": 10, "declared": 50_000}], [], {}
    )
    assert _fired(ctx, "SITEMAP_TOO_MANY_URLS") == []


def test_the_size_limit_is_measured_uncompressed():
    """The parser hands over the decompressed body, so a gzipped sitemap is judged by the
    document a search engine parses rather than by what travelled over the wire."""
    ctx = _Ctx()
    documents = [
        {
            "url": "https://example.com/big.xml.gz",
            "bytes": MAX_SITEMAP_BYTES_PER_FILE + 1,
            "declared": 10,
        }
    ]
    _check_protocol_limits(ctx, documents, [], {})
    fired = _fired(ctx, "SITEMAP_TOO_LARGE")
    assert len(fired) == 1
    assert fired[0][2]["limit"] == MAX_SITEMAP_BYTES_PER_FILE


def test_a_sitemap_inside_both_limits_reports_nothing():
    ctx = _Ctx()
    _check_protocol_limits(
        ctx, [{"url": "https://example.com/s.xml", "bytes": 2048, "declared": 120}], [], {}
    )
    assert ctx.added == []


def test_a_url_declared_in_two_sitemaps_names_both():
    ctx = _Ctx()
    summary: dict = {}
    entries = [
        {"loc": "https://example.com/a", "source": "https://example.com/sitemap-1.xml"},
        {"loc": "https://example.com/a", "source": "https://example.com/sitemap-2.xml"},
        {"loc": "https://example.com/b", "source": "https://example.com/sitemap-1.xml"},
    ]
    _check_protocol_limits(ctx, [], entries, summary)

    fired = _fired(ctx, "SITEMAP_URL_DUPLICATED")
    assert len(fired) == 1, "one finding per duplicated URL, not one per occurrence"
    assert fired[0][1] == "https://example.com/a"
    assert fired[0][2]["sitemaps"] == [
        "https://example.com/sitemap-1.xml",
        "https://example.com/sitemap-2.xml",
    ]
    assert summary["urls_in_multiple_sitemaps"] == 1


def test_the_same_url_twice_in_one_sitemap_is_not_a_cross_file_duplicate():
    """Two entries in one document is a different problem, and calling it this one would
    send somebody looking for a second sitemap that does not exist."""
    ctx = _Ctx()
    entries = [
        {"loc": "https://example.com/a", "source": "https://example.com/sitemap.xml"},
        {"loc": "https://example.com/a", "source": "https://example.com/sitemap.xml"},
    ]
    _check_protocol_limits(ctx, [], entries, {})
    assert _fired(ctx, "SITEMAP_URL_DUPLICATED") == []


def test_a_trailing_slash_only_difference_across_sitemaps_is_still_a_duplicate():
    """Same raw-string-diff shape as #145's SITEMAP_DESYNC: "/a" in one sitemap and "/a/"
    in another is one page declared twice, not two distinct URLs that happen to look
    alike."""
    ctx = _Ctx()
    summary: dict = {}
    entries = [
        {"loc": "https://example.com/a", "source": "https://example.com/sitemap-1.xml"},
        {"loc": "https://example.com/a/", "source": "https://example.com/sitemap-2.xml"},
    ]
    _check_protocol_limits(ctx, [], entries, summary)

    fired = _fired(ctx, "SITEMAP_URL_DUPLICATED")
    assert len(fired) == 1
    assert fired[0][2]["sitemaps"] == [
        "https://example.com/sitemap-1.xml",
        "https://example.com/sitemap-2.xml",
    ]
    assert summary["urls_in_multiple_sitemaps"] == 1
