"""Regression tests for the 20-agent review fixes (security, DOM, perf, parsing)."""

from __future__ import annotations

import gzip

import pytest

from seohead.sf.core import heuristics, sitemap_coverage as sitemap
from seohead.sf.core.aggregate import _fingerprint
from seohead.sf.core.models import Issue
from seohead.sf.core.rules import _path_of


# --- sitemap security -------------------------------------------------------
def test_fetch_rejects_non_http_schemes():
    # SSRF/file-read guard: never touch file://, ftp://, etc. (no network needed)
    assert sitemap._fetch("file:///etc/passwd", "ua", 1) is None
    assert sitemap._fetch("ftp://host/x", "ua", 1) is None


def test_gunzip_bomb_guarded(monkeypatch):
    monkeypatch.setattr(sitemap, "MAX_DECOMPRESSED_BYTES", 1000)
    bomb = gzip.compress(b"A" * 50_000)  # expands well past the lowered cap
    with pytest.raises(ValueError):
        sitemap._safe_gunzip(bomb)


def test_sitemap_rejects_dtd_and_entities():
    xxe = (
        b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]>'
        b"<urlset><url><loc>&e;</loc></url></urlset>"
    )
    assert sitemap._parse_sitemap_bytes(xxe, "ua", 1, set(), set()) == []


def test_sitemap_parses_clean_urlset():
    xml = (
        b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        b"<url><loc>https://example.com/a</loc><lastmod>2025-01-01</lastmod></url>"
        b"<url><loc>https://example.com/b</loc></url></urlset>"
    )
    out = sitemap._parse_sitemap_bytes(xml, "ua", 1, set(), {"x.com"})
    assert [e["loc"] for e in out] == ["https://example.com/a", "https://example.com/b"]
    assert out[0]["lastmod"] == "2025-01-01"


# --- heuristics: DOM index + metrics ---------------------------------------
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


# --- rules: path extraction strips query/fragment ---------------------------
def test_path_of_strips_query_and_fragment():
    assert _path_of("https://example.com/Path/Page?Q=UPPER#Frag") == "/Path/Page"
    assert _path_of("https://example.com/") == "/"


# --- aggregate: fingerprint stable regardless of (capped) locations ---------
def test_fingerprint_independent_of_locations():
    a = Issue(
        check="BROKEN_INTERNAL_LINK",
        severity="critical",
        source="s",
        message="m",
        target_url="https://x/p",
        status_code=404,
        locations=[{"source_url": "https://x/a"}],
    )
    b = Issue(
        check="BROKEN_INTERNAL_LINK",
        severity="critical",
        source="s",
        message="m",
        target_url="https://x/p",
        status_code=404,
        locations=[{"source_url": "https://x/a"}, {"source_url": "https://x/b"}],
    )
    assert _fingerprint(a) == _fingerprint(b)
