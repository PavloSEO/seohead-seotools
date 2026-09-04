"""Offline tests for custom extraction: CSS/XPath/regex fields with a bounded
budget (issue #20, part 2). No network access."""

import time

import pytest

from seohead.tools.custom_extract import run_extraction, run_extractor


def _doc(url, html, ok=True, rendered=False):
    return {"url": url, "ok": ok, "html": html, "rendered": rendered}


def test_css_mode_extracts_element_text():
    documents = [
        _doc("https://example.com/a", '<div class="price">$19.99</div>'),
        _doc("https://example.com/b", "<div>no price here</div>"),
    ]
    result = run_extractor(
        documents, {"name": "price", "mode": "css", "query": ".price", "output": "text"}
    )
    assert result["rows"][0] == {
        "url": "https://example.com/a",
        "values": ["$19.99"],
        "count": 1,
        "budget_exceeded": False,
    }
    assert result["rows"][1]["values"] == []


def test_css_mode_element_and_html_outputs():
    documents = [_doc("https://example.com/a", '<div class="x"><b>bold</b></div>')]
    element = run_extractor(documents, {"mode": "css", "query": ".x", "output": "element"})
    inner = run_extractor(documents, {"mode": "css", "query": ".x", "output": "html"})
    assert '<div class="x">' in element["rows"][0]["values"][0]
    assert inner["rows"][0]["values"][0] == "<b>bold</b>"


def test_xpath_mode_extracts_a_capture():
    documents = [_doc("https://example.com/a", "<html><body><h1>Title Here</h1></body></html>")]
    result = run_extractor(documents, {"mode": "xpath", "query": "//h1/text()", "output": "text"})
    assert result["rows"][0]["values"] == ["Title Here"]


def test_regex_mode_extracts_a_group():
    documents = [_doc("https://example.com/a", "counter id: UA-12345-1 end")]
    result = run_extractor(
        documents, {"mode": "regex", "query": r"UA-(\d+-\d+)", "output": "group", "group": 1}
    )
    assert result["rows"][0]["values"] == ["12345-1"]
    assert "raw HTML" in " ".join(result["notes"])  # the regex-vs-rendered caveat is surfaced


def test_pathological_regex_aborts_only_that_document_and_the_run_finishes():
    """Acceptance criterion: a pathological expression aborts that document and
    is reported, and the crawl (the whole extraction call) still finishes."""
    evil_html = "a" * 30 + "c"  # no trailing 'b' -> catastrophic backtracking
    documents = [
        _doc("https://example.com/ok1", "aaab"),
        _doc("https://example.com/evil", evil_html),
        _doc("https://example.com/ok2", "aaab"),
    ]
    started = time.monotonic()
    result = run_extraction(
        documents,
        [{"name": "evil", "mode": "regex", "query": r"(a+)+b", "output": "text"}],
        timeout_seconds=0.3,
    )
    elapsed = time.monotonic() - started
    # The call returned at all (the run "finished") well under a naive
    # exponential-backtrack duration, which would be many seconds for this input.
    assert elapsed < 3.0

    rows = {row["url"]: row for row in result["extractors"][0]["rows"]}
    assert rows["https://example.com/ok1"]["budget_exceeded"] is False
    assert rows["https://example.com/ok1"]["values"] == ["aaab"]
    assert rows["https://example.com/evil"]["budget_exceeded"] is True
    assert rows["https://example.com/evil"]["values"] == []
    assert rows["https://example.com/ok2"]["budget_exceeded"] is False
    assert rows["https://example.com/ok2"]["values"] == ["aaab"]
    assert result["extractors"][0]["aborted_pages"] == ["https://example.com/evil"]
    assert any("exceeded" in note for note in result["extractors"][0]["notes"])


def test_fetch_failures_are_excluded_from_the_denominator():
    documents = [
        _doc("https://example.com/a", "<p>x</p>"),
        _doc("https://example.com/b", "", ok=False),
    ]
    result = run_extractor(documents, {"mode": "css", "query": "p", "output": "text"})
    assert result["pages_considered"] == 1
    assert result["pages_excluded_fetch_failed"] == 1


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError, match="mode"):
        run_extractor([_doc("https://example.com/a", "<p>x</p>")], {"mode": "bogus", "query": "p"})


def test_output_not_valid_for_mode_is_rejected():
    with pytest.raises(ValueError, match="output"):
        run_extractor(
            [_doc("https://example.com/a", "<p>x</p>")],
            {"mode": "css", "query": "p", "output": "group"},
        )


def test_missing_query_is_rejected():
    with pytest.raises(ValueError, match="query"):
        run_extractor([_doc("https://example.com/a", "<p>x</p>")], {"mode": "css", "query": ""})


def test_run_extraction_applies_every_extractor():
    documents = [_doc("https://example.com/a", '<div class="price">$5</div><h1>Widget</h1>')]
    out = run_extraction(
        documents,
        [
            {"name": "price", "mode": "css", "query": ".price", "output": "text"},
            {"name": "title", "mode": "css", "query": "h1", "output": "text"},
        ],
    )
    assert out["ok"] is True
    names = [e["name"] for e in out["extractors"]]
    assert names == ["price", "title"]
