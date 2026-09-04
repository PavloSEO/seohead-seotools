"""Nested sitemap-index parsing, retry/failure tracking, SSRF + XXE guards."""

from __future__ import annotations

import gzip

import pytest

from seohead.sf.core import sitemap_coverage as S

NS = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'


def _index(*locs):
    items = "".join(f"<sitemap><loc>{u}</loc></sitemap>" for u in locs)
    return f"<sitemapindex {NS}>{items}</sitemapindex>".encode()


def _urlset(*locs):
    items = "".join(f"<url><loc>{u}</loc><lastmod>2025-01-01</lastmod></url>" for u in locs)
    return f"<urlset {NS}>{items}</urlset>".encode()


def test_two_level_nested_index(monkeypatch):
    # Root index -> two sub-indexes -> leaf URL sets.
    tree = {
        "https://example.com/index-a.xml": _index(
            "https://example.com/a-1.xml", "https://example.com/a-2.xml"
        ),
        "https://example.com/index-b.xml": _index("https://example.com/b-1.xml"),
        "https://example.com/a-1.xml": _urlset(
            "https://example.com/a/1", "https://example.com/a/2"
        ),
        "https://example.com/a-2.xml": _urlset("https://example.com/a/3"),
        "https://example.com/b-1.xml": _urlset("https://example.com/b/1"),
    }
    monkeypatch.setattr(S, "_fetch", lambda u, ua, t, retries=2: tree.get(u))
    root = _index("https://example.com/index-a.xml", "https://example.com/index-b.xml")
    fails: list[str] = []
    out = S._parse_sitemap_bytes(root, "ua", 1, set(), {"example.com"}, failures=fails)
    locs = sorted(e["loc"] for e in out)
    assert locs == [
        "https://example.com/a/1",
        "https://example.com/a/2",
        "https://example.com/a/3",
        "https://example.com/b/1",
    ]
    assert fails == []
    assert all(e["lastmod"] == "2025-01-01" for e in out)


def test_failed_child_is_tracked(monkeypatch):
    tree = {
        "https://example.com/a.xml": _urlset("https://example.com/1")
    }  # b.xml is intentionally missing to exercise failure tracking.
    monkeypatch.setattr(S, "_fetch", lambda u, ua, t, retries=2: tree.get(u))
    root = _index("https://example.com/a.xml", "https://example.com/b.xml")
    fails: list[str] = []
    out = S._parse_sitemap_bytes(root, "ua", 1, set(), {"example.com"}, failures=fails)
    assert [e["loc"] for e in out] == ["https://example.com/1"]
    assert fails == ["https://example.com/b.xml"]  # Do not silently drop failures.


def test_ssrf_blocks_foreign_host(monkeypatch):
    calls: list[str] = []

    def fake(u, ua, t, retries=2):
        calls.append(u)
        return _urlset("https://example.com/ok")

    monkeypatch.setattr(S, "_fetch", fake)
    root = _index("https://example.com/child.xml", "https://example.org/child.xml")
    S._parse_sitemap_bytes(root, "ua", 1, set(), {"example.com"}, failures=[])
    assert "https://example.com/child.xml" in calls
    assert "https://example.org/child.xml" not in calls  # Never fetch a foreign host.


def test_xxe_payload_rejected():
    xxe = (
        b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY e SYSTEM "file:///etc/passwd">]>'
        b"<urlset><url><loc>&e;</loc></url></urlset>"
    )
    assert S._parse_sitemap_bytes(xxe, "ua", 1, set(), set()) == []


def test_fetch_rejects_non_http_schemes():
    # SSRF/file-read guard: never touch file://, ftp://, etc. (no network needed)
    assert S._fetch("file:///etc/passwd", "ua", 1) is None
    assert S._fetch("ftp://host/x", "ua", 1) is None


def test_gunzip_bomb_guarded(monkeypatch):
    monkeypatch.setattr(S, "MAX_DECOMPRESSED_BYTES", 1000)
    bomb = gzip.compress(b"A" * 50_000)  # expands well past the lowered cap
    with pytest.raises(ValueError):
        S._safe_gunzip(bomb)


def test_sitemap_rejects_dtd_and_entities():
    xxe = (
        b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]>'
        b"<urlset><url><loc>&e;</loc></url></urlset>"
    )
    assert S._parse_sitemap_bytes(xxe, "ua", 1, set(), set()) == []


def test_sitemap_parses_clean_urlset():
    xml = (
        b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        b"<url><loc>https://example.com/a</loc><lastmod>2025-01-01</lastmod></url>"
        b"<url><loc>https://example.com/b</loc></url></urlset>"
    )
    out = S._parse_sitemap_bytes(xml, "ua", 1, set(), {"x.com"})
    assert [e["loc"] for e in out] == ["https://example.com/a", "https://example.com/b"]
    assert out[0]["lastmod"] == "2025-01-01"
