"""Relative URLs must resolve against ``<base href>``, not the page URL.

Without this the toolkit reports internal links that do not exist: sites that
ship a ``<base>`` tag (MODX and older CMS themes do) produced a flood of
phantom broken links that a browser fetches with a 200.
"""

from seohead.recon import regions
from seohead.tools import hreflang, page_facts, render
from seohead.tools.parser import document_base_url, parse_html

PAGE = "https://example.com/section/subsection/"


def _first_link(html: str, url: str = PAGE) -> str:
    return parse_html(html, url)["links"][0]["href"]


def test_absolute_base_wins_over_page_url():
    html = '<html><head><base href="https://example.com/"></head><body><a href="catalog/">c</a></body></html>'
    assert _first_link(html) == "https://example.com/catalog/"


def test_without_base_resolution_is_unchanged():
    html = '<html><body><a href="catalog/">c</a></body></html>'
    assert _first_link(html) == "https://example.com/section/subsection/catalog/"


def test_relative_base_is_resolved_against_the_page_url():
    html = '<html><head><base href="/shop/"></head><body><a href="x">c</a></body></html>'
    assert _first_link(html) == "https://example.com/shop/x"


def test_dot_dot_base_is_resolved_against_the_page_url():
    html = '<html><head><base href="../"></head><body><a href="x">c</a></body></html>'
    assert _first_link(html) == "https://example.com/section/x"


def test_base_without_trailing_slash_drops_its_last_segment():
    html = '<html><head><base href="https://example.com/shop"></head><body><a href="x">c</a></body></html>'
    assert _first_link(html) == "https://example.com/x"


def test_only_the_first_base_with_an_href_counts():
    html = (
        '<html><head><base target="_blank"><base href="/shop/">'
        '<base href="/other/"></head><body><a href="x">c</a></body></html>'
    )
    assert _first_link(html, "https://example.com/a/b/") == "https://example.com/shop/x"


def test_base_without_href_is_ignored():
    html = '<html><head><base target="_blank"></head><body><a href="catalog/">c</a></body></html>'
    assert _first_link(html) == "https://example.com/section/subsection/catalog/"


def test_external_flag_still_follows_the_page_host_not_the_base():
    """A base on another host must not reclassify the whole page as external."""
    html = '<html><head><base href="https://cdn.other.com/"></head><body><a href="x">c</a></body></html>'
    link = parse_html(html, "https://example.com/p/")["links"][0]
    assert link["href"] == "https://cdn.other.com/x"
    assert link["external"] is True


def test_canonical_resolves_against_the_base():
    html = (
        '<html><head><base href="https://example.com/">'
        '<link rel="canonical" href="catalog/"></head><body></body></html>'
    )
    assert parse_html(html, PAGE)["canonical"] == "https://example.com/catalog/"


def test_url_sources_resolve_against_the_base():
    html = '<html><head><base href="https://example.com/"></head><body><img src="img/a.png"></body></html>'
    parsed = parse_html(html, PAGE, {"url_sources": True})
    urls = [s["url"] for s in parsed["url_sources"]]
    assert "https://example.com/img/a.png" in urls


def test_hreflang_alternates_resolve_against_the_base():
    html = (
        '<html><head><base href="https://example.com/">'
        '<link rel="alternate" hreflang="en" href="en/"></head></html>'
    )
    assert hreflang.extract_hreflang(html, PAGE)[0]["href"] == "https://example.com/en/"


def test_render_link_collection_resolves_against_the_base():
    html = '<html><head><base href="https://example.com/"></head><body><a href="catalog/">c</a></body></html>'
    assert render._links(html, PAGE) == {"https://example.com/catalog/"}


def test_regions_link_collection_resolves_against_the_base():
    html = '<html><head><base href="https://example.com/"></head><body><a href="spb/">c</a></body></html>'
    found = regions.discover_regional_links(html, PAGE)
    assert any(item["url"].startswith("https://example.com/spb") for item in found)


def test_page_facts_breadcrumbs_resolve_against_the_base():
    html = (
        '<html><head><base href="https://example.com/"></head><body>'
        '<nav class="breadcrumbs"><a href="catalog/">Catalog</a></nav></body></html>'
    )
    facts = page_facts.extract(html, PAGE)
    crumbs = [c["url"] for c in facts["breadcrumbs"]]
    assert not crumbs or crumbs[0] == "https://example.com/catalog/"


def test_document_base_url_accepts_raw_html_and_parsed_markup():
    html = '<html><head><base href="/shop/"></head></html>'
    assert document_base_url(html, PAGE) == "https://example.com/shop/"
