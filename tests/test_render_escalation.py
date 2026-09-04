"""Selective rendering escalation and the pre-flight health-score gate (#18).

Pure orchestration: probe and render_fetch are always fakes here, so this
whole file runs with no network and no browser.
"""

from __future__ import annotations

from dataclasses import dataclass

from seohead.crawl import settings as crawl_config
from seohead.crawl.render_escalation import (
    EscalationResult,
    apply_rendered_evidence,
    escalate,
    select_samples,
    start_page_gate,
    url_pattern,
)


@dataclass
class _Page:
    url: str
    outlinks: int = 0
    external_outlinks: int = 0


# ── url_pattern / select_samples ─────────────────────────────────────────────


def test_numeric_path_segments_collapse_to_one_pattern():
    assert url_pattern("https://example.com/product/1") == url_pattern(
        "https://example.com/product/2"
    )


def test_slug_like_segments_collapse_too():
    assert url_pattern("https://example.com/blog/how-to-fix-pumps") == url_pattern(
        "https://example.com/blog/another-long-slug-here"
    )


def test_short_static_segments_do_not_collapse():
    assert url_pattern("https://example.com/about") != url_pattern("https://example.com/contact")


def test_query_and_fragment_are_ignored_in_the_pattern_key():
    assert url_pattern("https://example.com/x?a=1#top") == url_pattern("https://example.com/x")


def test_select_samples_caps_each_pattern_at_n():
    urls = [f"https://example.com/product/{i}" for i in range(10)]
    samples = select_samples(urls, sample_per_pattern=2)
    assert len(samples) == 1
    assert len(next(iter(samples.values()))) == 2


def test_select_samples_treats_zero_as_at_least_one():
    samples = select_samples(["https://example.com/"], sample_per_pattern=0)
    assert len(next(iter(samples.values()))) == 1


# ── start_page_gate ──────────────────────────────────────────────────────────


def test_zero_internal_links_requires_rendering():
    gate = start_page_gate("https://example.com/", 0, "<html><body>hi</body></html>")
    assert gate.requires_rendering is True
    assert "zero internal links" in gate.reason


def test_a_normal_start_page_does_not_require_rendering():
    gate = start_page_gate("https://example.com/", 5, "<html><body>hi</body></html>")
    assert gate.requires_rendering is False
    assert gate.reason == ""


def test_an_empty_spa_shell_requires_rendering_even_with_no_outlinks_check():
    html = '<html><body><div id="root"></div></body></html>'
    gate = start_page_gate("https://example.com/", 3, html)
    assert gate.requires_rendering is True
    assert "empty SPA shell" in gate.reason


def test_gate_works_with_no_html_at_all():
    """A resumed run that never re-fetched the start page still gets the outlink check."""
    gate = start_page_gate("https://example.com/", 0, "")
    assert gate.requires_rendering is True


# ── escalate() ───────────────────────────────────────────────────────────────


def _config(mode="js", sample_per_pattern=1, max_render_urls=100):
    resolved = crawl_config.load(
        overrides={
            "rendering.mode": mode,
            "rendering.escalation.sample_per_pattern": sample_per_pattern,
            "rendering.escalation.max_render_urls": max_render_urls,
        }
    )
    return resolved["rendering"]


def test_a_pattern_that_probes_clean_is_never_rendered():
    pages = [_Page(f"https://example.com/blog/{i}") for i in range(3)]

    def probe(_url):
        return {"ok": True, "needs_escalation": False}

    def render_fetch(_url):
        raise AssertionError("must not render a pattern that did not need it")

    result = escalate(
        pages,
        _config(),
        probe=probe,
        render_fetch=render_fetch,
        representation_label="rendered",
    )
    assert result.patterns_escalated == []
    assert result.render_requests == 0
    assert all(rep == "static" for rep in result.representations.values())


def test_an_escalated_pattern_renders_every_page_in_it_not_just_the_sample():
    pages = [_Page(f"https://example.com/blog/{i}") for i in range(5)]
    rendered_calls = []

    def probe(_url):
        return {"ok": True, "needs_escalation": True}

    def render_fetch(u):
        rendered_calls.append(u)
        return {"ok": True, "html": "<html><body>full</body></html>", "final_url": u}

    result = escalate(
        pages,
        _config(sample_per_pattern=1),
        probe=probe,
        render_fetch=render_fetch,
        representation_label="rendered",
    )
    assert result.patterns_sampled == 1
    assert result.patterns_escalated
    # Selective: only 1 probe request for the whole pattern (proves sampling).
    assert result.probe_requests == 1
    # But every page sharing the escalated pattern gets rendered.
    assert result.render_requests == 5
    assert set(rendered_calls) == {p.url for p in pages}
    assert all(rep == "rendered" for rep in result.representations.values())


def test_the_render_budget_is_a_separate_ceiling_from_the_sample():
    pages = [_Page(f"https://example.com/blog/{i}") for i in range(10)]

    def probe(_url):
        return {"ok": True, "needs_escalation": True}

    def render_fetch(u):
        return {"ok": True, "html": "<html></html>", "final_url": u}

    result = escalate(
        pages,
        _config(max_render_urls=3),
        probe=probe,
        render_fetch=render_fetch,
        representation_label="rendered",
    )
    assert result.render_requests == 3
    assert result.render_budget_exhausted is True


def test_only_patterns_that_probe_positive_are_escalated_others_stay_static():
    blog = [_Page(f"https://example.com/blog/{i}") for i in range(3)]
    docs = [_Page(f"https://example.com/docs/{i}") for i in range(3)]

    def probe(u):
        return {"ok": True, "needs_escalation": "/blog/" in u}

    def render_fetch(u):
        return {"ok": True, "html": "<html></html>", "final_url": u}

    result = escalate(
        blog + docs,
        _config(),
        probe=probe,
        render_fetch=render_fetch,
        representation_label="rendered",
    )
    assert all(result.representations[p.url] == "rendered" for p in blog)
    assert all(result.representations[p.url] == "static" for p in docs)


def test_empty_shell_probes_are_collected_regardless_of_escalation_outcome():
    pages = [_Page("https://example.com/")]

    def probe(_url):
        return {"ok": True, "needs_escalation": False, "empty_shell": "root"}

    result = escalate(
        pages,
        _config(),
        probe=probe,
        render_fetch=lambda u: {"ok": False},
        representation_label="rendered",
    )
    assert result.empty_shell_urls == ["https://example.com/"]


def test_a_failed_probe_is_not_counted_as_a_positive_signal():
    pages = [_Page("https://example.com/x")]

    def probe(_url):
        return {"ok": False}

    result = escalate(
        pages,
        _config(),
        probe=probe,
        render_fetch=lambda u: {"ok": False},
        representation_label="rendered",
    )
    assert result.patterns_escalated == []


def test_a_failed_render_fetch_leaves_the_page_static():
    pages = [_Page("https://example.com/x")]

    def probe(_url):
        return {"ok": True, "needs_escalation": True}

    def render_fetch(_url):
        return {"ok": False, "error": "timeout"}

    result = escalate(
        pages,
        _config(),
        probe=probe,
        render_fetch=render_fetch,
        representation_label="rendered",
    )
    assert result.representations["https://example.com/x"] == "static"
    assert result.rendered == {}


# ── apply_rendered_evidence ──────────────────────────────────────────────────


class _Edge:
    def __init__(self, source, destination):
        self.source = source
        self.destination = destination


def test_rendered_outlinks_are_the_union_with_raw_not_a_replacement():
    from seohead.crawl.collect import PageRecord

    record = PageRecord(url="https://example.com/", outlinks=1, external_outlinks=0)
    raw_links = [_Edge("https://example.com/", "https://example.com/only-in-raw")]
    rendered_html = (
        '<html><body><a href="/only-in-raw">a</a><a href="/only-after-js">b</a></body></html>'
    )
    result = EscalationResult()
    result.representations["https://example.com/"] = "rendered"
    result.rendered["https://example.com/"] = {
        "ok": True,
        "html": rendered_html,
        "final_url": "https://example.com/",
    }

    apply_rendered_evidence([record], raw_links, result)

    assert record.representation == "rendered"
    # Both the raw-only and the rendered-only link survive the merge.
    assert record.outlinks == 2


def test_a_page_never_rendered_is_left_untouched():
    from seohead.crawl.collect import PageRecord

    record = PageRecord(url="https://example.com/", title="Original")
    apply_rendered_evidence([record], [], EscalationResult())
    assert record.title == "Original"
    assert record.representation == "static"
