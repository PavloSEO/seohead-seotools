"""Unit tests for the pure (network-free) core functions."""

from seohead.tools import (
    clusterer,
    downloader,
    hreflang,
    optimizer,
    parser,
    redirects,
    robots,
    sitemap,
)

# ── redirects ────────────────────────────────────────────────────────────────


def test_generate_rules_nginx():
    rules = redirects.generate_rules([{"from": "/old", "to": "/new"}], "nginx")
    assert rules == ["rewrite ^/old$ /new permanent;"]


def test_generate_rules_apache():
    rules = redirects.generate_rules([{"old_url": "/a", "new_url": "/b"}], "apache")
    assert any("/a" in r and "/b" in r for r in rules)


def test_generate_rules_alias_keys():
    a = redirects.generate_rules([{"from": "/x", "to": "/y"}], "nginx")
    b = redirects.generate_rules([{"oldUrl": "/x", "newUrl": "/y"}], "nginx")
    assert a == b


# ── parser (pure parse_html) ─────────────────────────────────────────────────

_HTML = """<html><head><title>Hi</title>
<meta name="description" content="Desc">
<link rel="canonical" href="/canon">
<meta property="og:title" content="OG">
</head><body><h1>Head1</h1><h2>Head2</h2>
<a href="/in">internal</a>
<a href="https://other.tld/out" rel="nofollow">ext</a>
<a href="mailto:x@y.z">mail</a>
<p>hello world foo</p></body></html>"""


def test_parse_html_basics():
    r = parser.parse_html(_HTML, "https://site.tld/page")
    assert r["title"] == "Hi"
    assert r["meta_description"] == "Desc"
    assert r["canonical"] == "https://site.tld/canon"
    assert r["headings"]["h1"] == ["Head1"]
    assert r["word_count"] >= 3


def test_parse_html_links_classified():
    r = parser.parse_html(_HTML, "https://site.tld/page")
    hrefs = {ln["href"] for ln in r["links"]}
    assert "https://site.tld/in" in hrefs
    assert any(ln.get("nofollow") for ln in r["links"])
    assert not any("mailto" in ln["href"] for ln in r["links"])


def test_parse_html_options_off():
    r = parser.parse_html(_HTML, "https://site.tld/page", {"links": False, "text": False})
    assert r["links"] == []


# ── robots ───────────────────────────────────────────────────────────────────


def test_robots_wildcard_and_precedence():
    parsed = robots.parse_robots(
        "User-agent: *\nDisallow: /api/\nDisallow: /*?\nAllow: /api/public\nSitemap: https://s/x.xml"
    )
    assert parsed["sitemaps"] == ["https://s/x.xml"]
    assert robots.is_allowed(parsed, "/api/public/x") is True
    assert robots.is_allowed(parsed, "/api/secret") is False
    assert robots.is_allowed(parsed, "/blog?page=2") is False
    assert robots.is_allowed(parsed, "/blog") is True


def test_robots_end_anchor():
    parsed = robots.parse_robots("User-agent: *\nDisallow: /*.pdf$")
    assert robots.is_allowed(parsed, "/file.pdf") is False
    assert robots.is_allowed(parsed, "/file.pdf?x=1") is True


# ── sitemap (pure parse_sitemap) ─────────────────────────────────────────────


def test_parse_sitemap_urlset():
    xml = (
        b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        b"<url><loc>https://s/a</loc><lastmod>2026-01-01</lastmod></url>"
        b"<url><loc>https://s/b</loc></url></urlset>"
    )
    r = sitemap.parse_sitemap(xml, "https://s/")
    assert r["type"] == "urlset"
    assert len(r["urls"]) == 2


def test_parse_sitemap_index():
    xml = (
        b'<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        b"<sitemap><loc>https://s/child.xml</loc></sitemap></sitemapindex>"
    )
    r = sitemap.parse_sitemap(xml, "https://s/")
    assert r["type"] == "index"
    locs = [s["loc"] if isinstance(s, dict) else s for s in r["sitemaps"]]
    assert locs == ["https://s/child.xml"]


# ── hreflang ─────────────────────────────────────────────────────────────────


def test_hreflang_extract_and_validate():
    html = (
        '<link rel="alternate" hreflang="ru" href="/ru">'
        '<link rel="alternate" hreflang="en-US" href="/en">'
        '<link rel="alternate" hreflang="x-default" href="/">'
    )
    alts = hreflang.extract_hreflang(html, "https://s")
    assert len(alts) == 3
    assert hreflang.validate(alts, "https://s/ru") == []
    assert "no x-default alternate" in hreflang.validate(alts[:2], "")


# ── optimizer (pure helpers) ─────────────────────────────────────────────────


def test_compute_resize_fits_and_no_upscale():
    assert optimizer.compute_resize(2000, 1000, {"max_width": 1000}) == (1000, 500)
    assert optimizer.compute_resize(400, 300, {"max_width": 1000}) == (400, 300)


def test_downloader_host_only_url_gets_content_type_extension(tmp_path):
    target = downloader.target_path(
        "https://example.com/", str(tmp_path), "domain-path", "image/gif"
    )
    assert target == str(tmp_path / "example.com" / "example.com-image.gif")


# ── clusterer (local, needs sklearn) ─────────────────────────────────────────


def test_clusterer_groups_keywords():
    res = clusterer.run_clusterer(
        {
            "keywords": ["buy shoes", "cheap shoes", "seo audit", "technical seo audit"],
            "algorithm": "kmeans",
            "n_clusters": 2,
        }
    )
    assert res["count"] == 2
    assert sum(len(c["keywords"]) for c in res["clusters"]) == 4
