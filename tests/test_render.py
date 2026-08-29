"""Compare raw HTML with the DOM through pure functions, without launching Chromium."""

from __future__ import annotations

from seohead.tools.render import (
    _empty_shell,
    _jsonld_types,
    _links,
    _snapshot,
    _words,
    compare,
    render_check,
)

BASE = "https://example.com/"


def _snap(**kw):
    base = {
        "words": 400,
        "links": 30,
        "title": "Pumps",
        "h1": "Pumps",
        "canonical": "https://example.com/",
        "jsonld_types": ["Product"],
        "html_bytes": 5000,
    }
    base.update(kw)
    return base


# ── Document snapshot ────────────────────────────────────────────────────────


def test_scripts_and_styles_are_not_content():
    """Inline JavaScript and CSS must not inflate the visible word count."""
    html = "<body><script>var a=1;var b=2;</script><style>.x{color:red}</style><p>visible text here</p></body>"
    assert _words(html) == 3


def test_only_internal_links_are_counted():
    html = (
        '<a href="/catalog">Catalog</a><a href="https://example.com/about">About</a>'
        '<a href="https://example.org/external">External</a><a href="#top">Top</a>'
        '<a href="tel:+79001112233">Phone</a>'
    )
    assert _links(html, BASE) == {"https://example.com/catalog", "https://example.com/about"}


def test_jsonld_types_are_pulled_from_nested_graph():
    html = (
        '<script type="application/ld+json">'
        '{"@graph":[{"@type":"Organization"},{"@type":["Product","Offer"]}]}</script>'
    )
    assert _jsonld_types(html) == ["Offer", "Organization", "Product"]


def test_broken_jsonld_is_skipped_not_fatal():
    assert _jsonld_types('<script type="application/ld+json">{broken</script>') == []


def test_empty_spa_shell_is_detected():
    for shell in ("root", "app", "__next", "__nuxt"):
        assert _empty_shell(f'<body><div id="{shell}"></div></body>') == shell


def test_shell_with_content_is_not_an_empty_shell():
    assert _empty_shell('<body><div id="root"><h1>Already rendered</h1></div></body>') is None


def test_snapshot_is_computed_the_same_way_for_both_sides():
    html = "<html><head><title>T</title></head><body><h1>H</h1><p>one two three</p></body></html>"
    snap = _snapshot(html, BASE)
    assert snap["title"] == "T" and snap["h1"] == "H" and snap["words"] >= 3


# ── Findings ─────────────────────────────────────────────────────────────────


def test_empty_shell_is_the_headline_finding():
    out = compare(_snap(words=5), _snap(words=800), shell="root")
    assert "empty <div" in out[0]
    assert "receives an empty page" in out[0]


def test_text_appearing_only_after_js_is_reported_with_a_share():
    out = compare(_snap(words=200), _snap(words=1000))
    assert any("80% of page copy appears only after JavaScript" in f for f in out)


def test_small_js_additions_are_not_alarming():
    """A five-percent copy increase is likely a widget, not a rendering problem."""
    out = compare(_snap(words=950), _snap(words=1000))
    assert not any("page copy appears only after JavaScript" in f for f in out)


def test_links_invisible_without_js_are_reported():
    out = compare(_snap(links=0), _snap(links=40))
    assert any("internal links appear" in f for f in out)


def test_title_rewritten_by_script_is_flagged():
    out = compare(_snap(title="Loading…"), _snap(title="Buy CDM Pumps"))
    assert any("title changes after JavaScript" in f for f in out)


def test_canonical_drawn_by_script_is_flagged():
    out = compare(_snap(canonical=""), _snap(canonical="https://example.com/x"))
    assert any("canonical" in f for f in out)


def test_schema_added_only_after_js_is_flagged():
    out = compare(_snap(jsonld_types=[]), _snap(jsonld_types=["Product", "BreadcrumbList"]))
    assert any("Schema.org types appear only after JavaScript" in f for f in out)
    assert any("BreadcrumbList" in f for f in out)


def test_identical_pages_get_an_explicit_all_clear():
    out = compare(_snap(), _snap())
    assert len(out) == 1 and "materially equivalent" in out[0]


# ── Boundaries ───────────────────────────────────────────────────────────────


def test_empty_url_is_data_not_a_crash():
    assert render_check("")["ok"] is False
    assert render_check("   ")["ok"] is False


def test_missing_playwright_is_reported_with_the_install_command(monkeypatch):
    """A missing browser is result data and includes the exact install command."""
    import builtins

    real_import = builtins.__import__

    def fake(name, *a, **kw):
        if name.startswith("playwright"):
            raise ImportError("no playwright")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", fake)
    r = render_check("https://example.com/")
    assert r["ok"] is False and "Playwright" in r["error"]
    assert "playwright install chromium" in r["install"]


def test_all_clear_is_a_single_shared_constant():
    """The shared all-clear constant keeps ``js_dependent`` and findings aligned."""
    from seohead.tools.render import ALL_CLEAR

    assert compare(_snap(), _snap()) == [ALL_CLEAR]


def test_lcp_is_collected_by_a_buffered_observer():
    """A buffered pre-navigation observer captures LCP when the entry API is empty."""
    from seohead.tools.render import _CLS_INIT_JS, _METRICS_JS

    assert "largest-contentful-paint" in _CLS_INIT_JS
    assert "buffered: true" in _CLS_INIT_JS
    assert "__seohead_lcp" in _METRICS_JS
