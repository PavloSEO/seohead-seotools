"""Test URL-bearing attributes beyond ``<a href>``."""

from seohead.tools.parser import parse_html


def _sources(html: str) -> list[dict]:
    r = parse_html(
        html, "https://example.com/", {"url_sources": True, "links": False, "text": False}
    )
    return r["url_sources"]


def test_srcset_yields_multiple_urls():
    src = _sources('<img src="/a.jpg" srcset="/a.jpg 1x, /b.jpg 2x">')
    urls = {s["url"] for s in src if s["tag"] == "img"}
    assert "https://example.com/a.jpg" in urls
    assert "https://example.com/b.jpg" in urls


def test_form_and_button_formaction():
    src = _sources('<form action="/submit"><button formaction="/alt">go</button></form>')
    urls = {s["url"] for s in src}
    assert "https://example.com/submit" in urls
    assert "https://example.com/alt" in urls


def test_a_ping_splits_into_multiple_urls():
    src = _sources('<a ping="https://tracker.example/p1 https://tracker.example/p2">x</a>')
    ping_urls = [s["url"] for s in src if s["attr"] == "ping"]
    assert "https://tracker.example/p1" in ping_urls
    assert "https://tracker.example/p2" in ping_urls


def test_cite_on_blockquote_and_meta_refresh():
    src = _sources(
        '<blockquote cite="https://q.example/orig">q</blockquote>'
        '<meta http-equiv="refresh" content="0;url=/moved">'
    )
    urls = {s["url"] for s in src}
    assert "https://q.example/orig" in urls
    assert "https://example.com/moved" in urls


def test_itemtype_collected():
    src = _sources('<div itemtype="https://schema.org/Product">p</div>')
    assert any(s["url"] == "https://schema.org/Product" and s["attr"] == "itemtype" for s in src)


def test_data_and_fragment_and_mailto_skipped():
    src = _sources(
        '<img src="data:image/png;base64,xx"><a href="#frag">x</a><img src="mailto:a@b.c">'
    )
    urls = {s["url"] for s in src}
    assert not any("data:" in u for u in urls)
    assert not any(u.endswith("#frag") for u in urls)


def test_url_sources_off_by_default():
    r = parse_html('<img src="/a.jpg">', "https://example.com/")
    assert "url_sources" not in r  # The disabled option preserves backward compatibility.
