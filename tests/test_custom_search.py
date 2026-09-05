"""Offline tests for custom search: a query language over a crawled corpus
(issue #20, part 1). No network access."""

import pytest

from seohead.tools.custom_search import run_filter, run_search


def _doc(url, html=None, ok=True, text=None, rendered=False):
    return {"url": url, "ok": ok, "html": html, "text": text, "rendered": rendered}


def test_not_contains_reports_exactly_the_pages_lacking_the_string():
    """Acceptance criterion: a fixture corpus of 900-ish pages, some missing a
    banner; failed fetches must be excluded from the denominator, not counted
    as missing."""
    documents = (
        [
            _doc(f"https://example.com/with/{i}", html="<div>consent-banner</div>")
            for i in range(1, 861)
        ]
        + [
            _doc(f"https://example.com/without/{i}", html="<div>no banner here</div>")
            for i in range(1, 41)
        ]
        + [_doc(f"https://example.com/failed/{i}", ok=False) for i in range(1, 6)]
    )
    result = run_filter(
        documents,
        {
            "name": "consent",
            "mode": "not_contains",
            "kind": "text",
            "scope": "raw",
            "query": "consent-banner",
        },
    )
    assert result["pages_considered"] == 900  # 860 + 40, the fetched corpus
    assert result["pages_excluded_fetch_failed"] == 5
    assert result["count"] == 40
    assert set(result["matching_pages"]) == {
        f"https://example.com/without/{i}" for i in range(1, 41)
    }
    # A failed fetch must never appear as "missing" evidence.
    assert not any("failed" in u for u in result["matching_pages"])


def test_contains_reports_the_presence_set():
    documents = [
        _doc("https://example.com/a", html="<script>gtag('config')</script>"),
        _doc("https://example.com/b", html="<p>nothing here</p>"),
    ]
    result = run_filter(
        documents, {"mode": "contains", "kind": "text", "scope": "raw", "query": "gtag("}
    )
    assert result["matching_pages"] == ["https://example.com/a"]
    assert result["fraction"] == 0.5


def test_regex_kind_supports_a_pattern_query():
    documents = [
        _doc("https://example.com/a", html="phone: +1-555-000-1111"),
        _doc("https://example.com/b", html="no phone here"),
    ]
    result = run_filter(
        documents,
        {"mode": "contains", "kind": "regex", "scope": "raw", "query": r"\+1-555-\d{3}-\d{4}"},
    )
    assert result["matching_pages"] == ["https://example.com/a"]


def test_text_scope_uses_visible_text_not_markup():
    documents = [_doc("https://example.com/a", html="<script>trackingId</script><p>Hello</p>")]
    raw = run_filter(
        documents, {"mode": "contains", "kind": "text", "scope": "raw", "query": "trackingId"}
    )
    visible = run_filter(
        documents, {"mode": "contains", "kind": "text", "scope": "text", "query": "trackingId"}
    )
    assert raw["count"] == 1  # present in raw source
    assert visible["count"] == 0  # not in visible text (it's inside <script>)


def test_element_scope_targets_a_named_element():
    documents = [
        _doc("https://example.com/a", html='<div class="price">$19.99</div>'),
        _doc("https://example.com/b", html="<div>no price div</div>"),
    ]
    result = run_filter(
        documents,
        {
            "mode": "not_contains",
            "kind": "regex",
            "scope": "element",
            "selector": ".price",
            "query": r"\$\d",
        },
    )
    # /b has no .price element at all -> empty target -> counted as lacking it.
    assert result["matching_pages"] == ["https://example.com/b"]


def test_xpath_scope_targets_a_named_node():
    documents = [
        _doc("https://example.com/a", html="<html><body><h1>Special Title</h1></body></html>"),
        _doc("https://example.com/b", html="<html><body><h1>Other</h1></body></html>"),
    ]
    result = run_filter(
        documents,
        {
            "mode": "contains",
            "kind": "text",
            "scope": "xpath",
            "selector": "//h1/text()",
            "query": "Special",
        },
    )
    assert result["matching_pages"] == ["https://example.com/a"]


def test_xpath_scope_uses_the_full_string_value_of_matched_elements():
    result = run_filter(
        [_doc("https://example.com/a", html="<h1><strong>Special</strong> Title</h1>")],
        {
            "mode": "contains",
            "scope": "xpath",
            "selector": "//h1",
            "query": "Special Title",
        },
    )
    assert result["matching_pages"] == ["https://example.com/a"]


def test_xpath_scope_without_a_selector_is_rejected():
    with pytest.raises(ValueError, match="selector"):
        run_filter(
            [_doc("https://example.com/a", html="<h1>x</h1>")],
            {"mode": "contains", "scope": "xpath", "query": "x"},
        )


def test_representation_reports_static_or_rendered():
    static_docs = [_doc("https://example.com/a", html="<p>x</p>", rendered=False)]
    rendered_docs = [_doc("https://example.com/a", html="<p>x</p>", rendered=True)]
    mixed_docs = static_docs + rendered_docs

    assert (
        run_filter(static_docs, {"mode": "contains", "scope": "raw", "query": "x"})[
            "representation"
        ]
        == "static_markup"
    )
    assert (
        run_filter(rendered_docs, {"mode": "contains", "scope": "raw", "query": "x"})[
            "representation"
        ]
        == "rendered_dom"
    )
    assert run_filter(mixed_docs, {"mode": "contains", "scope": "raw", "query": "x"})[
        "representation"
    ] == [
        "rendered_dom",
        "static_markup",
    ]


def test_unknown_scope_is_rejected():
    with pytest.raises(ValueError, match="scope"):
        run_filter(
            [_doc("https://example.com/a", html="x")],
            {"mode": "contains", "scope": "bogus", "query": "x"},
        )


@pytest.mark.parametrize(
    ("scope", "selector", "query", "error"),
    [
        ("element", "div[", "banner", "invalid CSS selector"),
        ("xpath", "//*[", "banner", "invalid XPath expression"),
        ("raw", "", "(", "invalid regular expression"),
    ],
)
def test_malformed_filter_expressions_are_rejected_before_absence_is_reported(
    scope, selector, query, error
):
    with pytest.raises(ValueError, match=error):
        run_filter(
            [_doc("https://example.com/a", html="<p>banner</p>")],
            {
                "mode": "not_contains",
                "kind": "regex" if query == "(" else "text",
                "scope": scope,
                "selector": selector,
                "query": query,
            },
        )


def test_run_search_applies_every_filter():
    documents = [_doc("https://example.com/a", html="foo bar")]
    out = run_search(
        documents,
        [
            {"name": "foo", "mode": "contains", "scope": "raw", "query": "foo"},
            {"name": "baz", "mode": "contains", "scope": "raw", "query": "baz"},
        ],
    )
    assert out["ok"] is True
    assert [f["name"] for f in out["filters"]] == ["foo", "baz"]
    assert out["filters"][0]["count"] == 1
    assert out["filters"][1]["count"] == 0


def test_empty_corpus_reports_zero_not_a_division_error():
    result = run_filter([], {"mode": "not_contains", "scope": "raw", "query": "x"})
    assert result["pages_considered"] == 0
    assert result["fraction"] == 0.0
    assert result["matching_pages"] == []
