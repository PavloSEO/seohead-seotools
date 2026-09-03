"""List mode: fetch an explicit URL list, project it, audit it.

Network-free throughout — every response is supplied by a fake fetcher.
"""

import json
from pathlib import Path

import pytest

from seohead.crawl.collect import collect_urls as _collect_urls
from seohead.crawl.evidence import UNAVAILABLE_FRAMES, build_evidence
from seohead.crawl.throttle import Throttle


def collect_urls(urls, **kw):
    """Never sleep for real in tests; back-off behaviour is asserted directly."""
    kw.setdefault("sleeper", lambda _seconds: None)
    return _collect_urls(urls, **kw)


HTML = """<html><head><base href="https://example.com/">
<title>Catalog</title><meta name="description" content="d">
<link rel="canonical" href="catalog/">
<script type="application/ld+json">{"@type":"Product"}</script>
</head><body><h1>Catalog</h1><a href="catalog/x">x</a></body></html>"""


class FakeResponse:
    def __init__(self, text="", status_code=200, headers=None):
        self.text = text
        self.status_code = status_code
        self.headers = headers or {"content-type": "text/html; charset=utf-8"}


def _fetch(mapping):
    def fetcher(url):
        value = mapping[url]
        if isinstance(value, Exception):
            raise value
        return value

    return fetcher


def test_collects_in_the_order_given_and_deduplicates():
    urls = ["https://example.com/a", "https://example.com/b", "https://example.com/a"]
    mapping = {u: FakeResponse(HTML) for u in urls}
    result = collect_urls(urls, fetcher=_fetch(mapping))
    assert [p.url for p in result.pages] == ["https://example.com/a", "https://example.com/b"]


def test_parses_against_the_document_base(tmp_path):
    """The <base href> fix must hold here too, or list mode invents 404s."""
    result = collect_urls(
        ["https://example.com/section/page"],
        fetcher=_fetch({"https://example.com/section/page": FakeResponse(HTML)}),
    )
    page = result.pages[0]
    assert page.canonical == "https://example.com/catalog/"
    assert page.title == "Catalog"
    assert page.h1 == "Catalog"


def test_reports_json_ld_found_but_unparsed_rather_than_absent():
    """A malformed block must not be reported as "no structured data"."""
    broken = '<html><head><script type="application/ld+json">{ /* c */ }</script></head><body></body></html>'
    result = collect_urls(
        ["https://example.com/"], fetcher=_fetch({"https://example.com/": FakeResponse(broken)})
    )
    page = result.pages[0]
    assert page.jsonld_blocks_found == 1
    assert page.jsonld_blocks_parsed == 0


def test_rows_are_written_as_they_are_collected(tmp_path):
    """An interrupted run must leave behind what it already had."""
    out = tmp_path / "pages.jsonl"
    urls = [f"https://example.com/{i}" for i in range(3)]
    collect_urls(urls, fetcher=_fetch({u: FakeResponse(HTML) for u in urls}), out_path=str(out))
    lines = [json.loads(line) for line in out.read_text().splitlines()]
    assert [row["url"] for row in lines] == urls


def test_a_timeout_backs_off_instead_of_retrying_immediately():
    urls = ["https://example.com/a", "https://example.com/b"]
    mapping = {urls[0]: TimeoutError("read timed out"), urls[1]: FakeResponse(HTML)}
    result = collect_urls(urls, fetcher=_fetch(mapping))
    assert "timed out" in result.pages[0].error


def test_repeated_timeouts_stop_the_run_and_mark_it_partial():
    urls = [f"https://example.com/{i}" for i in range(8)]
    mapping = {u: TimeoutError("connection timed out") for u in urls}
    result = collect_urls(urls, fetcher=_fetch(mapping))
    assert result.partial is True
    assert "timeouts" in result.stopped_reason
    assert len(result.pages) < len(urls), "must stop rather than walk the whole list"


def test_url_limit_marks_the_result_partial():
    urls = [f"https://example.com/{i}" for i in range(5)]
    result = collect_urls(urls, max_urls=2, fetcher=_fetch({u: FakeResponse(HTML) for u in urls}))
    assert len(result.pages) == 2
    assert result.partial is True


def test_an_oversized_response_is_not_reported_as_unreachable():
    big = "<html><body>" + ("x" * (6 * 1024 * 1024)) + "</body></html>"
    result = collect_urls(
        ["https://example.com/big"],
        fetcher=_fetch({"https://example.com/big": FakeResponse(big)}),
    )
    page = result.pages[0]
    assert page.status_code == 200
    assert "too large" in page.error


# ── throttle ────────────────────────────────────────────────────────────────


def test_latency_widens_the_delay():
    t = Throttle()
    t.record_response(1.2, ok=True)
    first = t.delay
    t.record_response(16.4, ok=True)
    assert t.delay > first


def test_a_fast_error_never_reduces_the_delay():
    t = Throttle()
    t.record_response(10.0, ok=True)
    before = t.delay
    t.record_response(0.01, ok=False)
    assert t.delay >= before


def test_a_timeout_is_the_strongest_signal():
    t = Throttle(min_delay=0.1)
    t.record_response(1.0, ok=True)
    before = t.delay
    t.record_timeout()
    assert t.delay > before * 2


def test_the_delay_is_bounded():
    t = Throttle(min_delay=1.0)
    for _ in range(20):
        t.record_timeout()
    assert t.delay <= 60.0


# ── projection ──────────────────────────────────────────────────────────────


def test_projection_declares_what_list_mode_cannot_measure():
    result = collect_urls(
        ["https://example.com/"], fetcher=_fetch({"https://example.com/": FakeResponse(HTML)})
    )
    evidence = build_evidence(result)
    assert evidence["found"] == ["internal_all"]
    assert set(evidence["missing"]) == set(UNAVAILABLE_FRAMES)
    assert "Closest Similarity Match" in evidence["unmeasured_columns"]


def test_projection_uses_the_headers_the_analyzer_resolves_by():
    result = collect_urls(
        ["https://example.com/"], fetcher=_fetch({"https://example.com/": FakeResponse(HTML)})
    )
    frame = build_evidence(result)["frames"]["internal_all"]
    for column in ("Address", "Status Code", "Title 1", "H1-1", "Indexability"):
        assert column in frame.columns


@pytest.mark.parametrize(
    "status,expected",
    [(200, "Indexable"), (301, "Non-Indexable"), (404, "Non-Indexable"), (500, "Non-Indexable")],
)
def test_indexability_follows_the_status(status, expected):
    body = "<html><head><title>t</title></head><body></body></html>"
    result = collect_urls(
        ["https://example.com/"],
        fetcher=_fetch({"https://example.com/": FakeResponse(body, status_code=status)}),
    )
    frame = build_evidence(result)["frames"]["internal_all"]
    assert frame.iloc[0]["Indexability"] == expected


# ── end to end through the analyzer ─────────────────────────────────────────


def test_a_collected_list_audits_and_declares_its_gaps():
    """The projection must reach a schema-valid audit with honest skips."""
    import json

    import jsonschema

    from seohead.sf.config import load_config
    from seohead.sf.core.aggregate import aggregate
    from seohead.sf.core.context import AuditContext
    from seohead.sf.core.loader import LoadedExports
    from seohead.sf.core.rules import run_rules

    urls = [f"https://example.com/{n}" for n in range(3)]
    result = collect_urls(urls, fetcher=_fetch({u: FakeResponse(HTML) for u in urls}))
    evidence = build_evidence(result)

    exports = LoadedExports()
    exports.frames.update(evidence["frames"])
    exports.found = list(evidence["found"])
    exports.missing = list(evidence["missing"])

    ctx = AuditContext(exports, load_config(None))
    ctx.skip_unsupported(set(exports.frames))
    run_rules(ctx)
    audit = aggregate(
        ctx,
        {"input_mode": "crawl-list", "generated_at": "2026-09-03T00:00:00Z"},
        {},
        {},
    ).to_json()

    schema_path = Path("seohead/sf/schema/audit.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(json.loads(json.dumps(audit)), schema)
    assert audit["summary"]["totals"]["urls_crawled"] == 3
    skipped = {s["id"] for s in audit["run"]["checks_skipped"]}
    assert skipped, "a projection with declared gaps must skip something"
    assert audit["summary"]["check_coverage"]["checks_silent"] >= 0


def test_the_collector_never_imports_the_analyzer():
    """The boundary is a gate, not a convention."""
    import re
    from pathlib import Path

    forbidden = re.compile(r"^\s*(from|import)\s+seohead\.(sf|servers|cli)\b", re.M)
    for path in Path("seohead/crawl").glob("*.py"):
        assert not forbidden.search(path.read_text(encoding="utf-8")), path


def test_the_analyzer_never_imports_the_collector():
    import re
    from pathlib import Path

    forbidden = re.compile(r"^\s*(from|import)\s+seohead\.crawl\b", re.M)
    for path in Path("seohead/sf").rglob("*.py"):
        assert not forbidden.search(path.read_text(encoding="utf-8")), path
