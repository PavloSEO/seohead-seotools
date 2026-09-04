"""A crawl that stops partway resumes from its checkpoint instead of
restarting. No network — the fetcher and clock are both fakes."""

import json

from seohead.crawl import state as crawl_state
from seohead.crawl.spider import crawl_site

ROBOTS_OK = "User-agent: *\n"


class FakeResponse:
    def __init__(self, text="", status_code=200, headers=None):
        self.text = text
        self.status_code = status_code
        self.headers = headers or {"content-type": "text/html; charset=utf-8"}


def page(*links, title="t"):
    body = "".join(f'<a href="{h}">{h}</a>' for h in links)
    return FakeResponse(
        f"<html><head><title>{title}</title></head><body><h1>{title}</h1>{body}</body></html>"
    )


SITE = {
    "https://example.com/robots.txt": FakeResponse(
        ROBOTS_OK, headers={"content-type": "text/plain"}
    ),
    "https://example.com/": page("/a", "/b"),
    "https://example.com/a": page("/c"),
    "https://example.com/b": page(),
    "https://example.com/c": page(),
}


def _fetcher(mapping, hits=None):
    def fetch(url):
        if hits is not None:
            hits.append(url)
        value = mapping.get(url)
        if value is None:
            return FakeResponse("", status_code=404)
        if isinstance(value, Exception):
            raise value
        return value

    return fetch


def test_a_url_limit_stop_checkpoints_the_frontier(tmp_path):
    state_path = str(tmp_path / "state.json")
    result = crawl_site(
        "https://example.com/",
        fetcher=_fetcher(SITE),
        sleeper=lambda _s: None,
        min_delay=0,
        max_urls=1,
        state_path=state_path,
    )
    assert result.partial is True
    assert result.finish_reason == "url_limit"
    assert result.resumed is False

    with open(state_path, encoding="utf-8") as fh:
        saved = json.load(fh)
    assert saved["schema_version"] == crawl_state.SCHEMA_VERSION
    # The root page enqueued /a and /b; neither was fetched yet.
    queued = {u for u, _d in saved["queue"]}
    assert queued == {"https://example.com/a", "https://example.com/b"}


def test_resuming_does_not_refetch_completed_urls(tmp_path):
    state_path = str(tmp_path / "state.json")
    out_path = str(tmp_path / "pages.jsonl")

    first = crawl_site(
        "https://example.com/",
        fetcher=_fetcher(SITE),
        sleeper=lambda _s: None,
        min_delay=0,
        max_urls=1,
        state_path=state_path,
        out_path=out_path,
    )
    assert {p.url for p in first.pages} == {"https://example.com/"}

    hits = []
    second = crawl_site(
        "https://example.com/",
        fetcher=_fetcher(SITE, hits=hits),
        sleeper=lambda _s: None,
        min_delay=0,
        max_urls=50,
        state_path=state_path,
        out_path=out_path,
    )
    assert second.resumed is True
    # The root page was never asked for again — only robots.txt (refetched
    # every run, deliberately, since it can change) and what was still queued.
    assert "https://example.com/" not in hits
    assert set(hits) == {
        "https://example.com/robots.txt",
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    }
    # The final result carries the whole crawl, first run's page included.
    assert {p.url for p in second.pages} == {
        "https://example.com/",
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    }
    assert second.finish_reason == "finished"
    assert second.partial is False

    # A fully finished crawl has nothing left to resume.
    assert not (tmp_path / "state.json").exists()


def test_a_finished_crawl_leaves_no_checkpoint(tmp_path):
    state_path = str(tmp_path / "state.json")
    crawl_site(
        "https://example.com/",
        fetcher=_fetcher(SITE),
        sleeper=lambda _s: None,
        min_delay=0,
        max_urls=50,
        state_path=state_path,
    )
    assert not (tmp_path / "state.json").exists()


def test_a_config_change_between_runs_starts_fresh_not_mixed(tmp_path):
    state_path = str(tmp_path / "state.json")
    crawl_site(
        "https://example.com/",
        fetcher=_fetcher(SITE),
        sleeper=lambda _s: None,
        min_delay=0,
        max_urls=1,
        state_path=state_path,
        config_fingerprint="scope-a",
    )
    result = crawl_site(
        "https://example.com/",
        fetcher=_fetcher(SITE),
        sleeper=lambda _s: None,
        min_delay=0,
        max_urls=1,
        state_path=state_path,
        config_fingerprint="scope-b",
    )
    assert result.resumed is False
    assert "changed" in result.resume_note


def test_a_keyboard_interrupt_stops_gracefully_and_requeues_the_url(tmp_path):
    state_path = str(tmp_path / "state.json")

    def fetch(url):
        if url == "https://example.com/a":
            raise KeyboardInterrupt
        return SITE.get(url, FakeResponse("", status_code=404))

    result = crawl_site(
        "https://example.com/",
        fetcher=fetch,
        sleeper=lambda _s: None,
        min_delay=0,
        max_urls=50,
        state_path=state_path,
    )
    assert result.finish_reason == "interrupted"
    assert result.partial is True

    with open(state_path, encoding="utf-8") as fh:
        saved = json.load(fh)
    queued = {u for u, _d in saved["queue"]}
    assert "https://example.com/a" in queued, "the interrupted URL must be retried on resume"


def test_max_seconds_stops_the_crawl_with_a_duration_finish_reason():
    ticking = {"t": 0.0}

    def fake_clock():
        ticking["t"] += 2  # each check sees two seconds pass
        return ticking["t"]

    result = crawl_site(
        "https://example.com/",
        fetcher=_fetcher(SITE),
        sleeper=lambda _s: None,
        min_delay=0,
        max_urls=50,
        max_seconds=5,
        clock=fake_clock,
    )
    assert result.finish_reason == "duration_limit"
    assert result.partial is True
    assert len(result.pages) < 4, "must stop well before exhausting the site"


# ── #141: links, excluded and the query-variant budget must survive a resume ─

SITE_WITH_EXCLUSIONS = {
    "https://example.com/robots.txt": FakeResponse(
        ROBOTS_OK + "Disallow: /private/\n", headers={"content-type": "text/plain"}
    ),
    "https://example.com/": page("/a", "/b", "/private/", "https://other.example/x"),
    "https://example.com/a": page("/c"),
    "https://example.com/b": page(),
    "https://example.com/c": page(),
}


def test_a_resumed_crawl_reports_the_same_links_and_excluded_as_an_uninterrupted_one(tmp_path):
    """Issue #141: result.links and result.excluded used to start over at [] / {} on every
    resumed call, so only what happened after the checkpoint survived into the final report."""
    full = crawl_site(
        "https://example.com/",
        fetcher=_fetcher(SITE_WITH_EXCLUSIONS),
        sleeper=lambda _s: None,
        min_delay=0,
        max_urls=50,
        config_fingerprint="fp",
    )
    assert full.partial is False

    out_dir = tmp_path / "run"
    out_dir.mkdir()
    state_path = str(out_dir / "state.json")
    links_path = str(out_dir / "links.jsonl")

    part = crawl_site(
        "https://example.com/",
        fetcher=_fetcher(SITE_WITH_EXCLUSIONS),
        sleeper=lambda _s: None,
        min_delay=0,
        max_urls=1,
        state_path=state_path,
        links_path=links_path,
        config_fingerprint="fp",
    )
    assert part.partial is True
    resumed = crawl_site(
        "https://example.com/",
        fetcher=_fetcher(SITE_WITH_EXCLUSIONS),
        sleeper=lambda _s: None,
        min_delay=0,
        max_urls=50,
        state_path=state_path,
        links_path=links_path,
        config_fingerprint="fp",
    )
    assert resumed.resumed is True
    assert resumed.partial is False

    def edges(result):
        return sorted((e.source, e.destination) for e in result.links)

    assert edges(resumed) == edges(full)
    assert resumed.excluded == full.excluded
    assert full.excluded == {"outside_host": 1, "blocked_by_robots": 1}


def test_a_resumed_query_variant_budget_is_not_per_call(tmp_path):
    """Issue #141: max_query_variants_per_path is a safety cap against faceted-navigation
    explosion. It must count variants across the whole resumed crawl, not reset to zero on
    every call — otherwise a crawl checkpointed even once stops capping anything."""
    site = {
        "https://example.com/robots.txt": FakeResponse(
            ROBOTS_OK, headers={"content-type": "text/plain"}
        ),
        # Two variants discovered from the start page...
        "https://example.com/": page("/search?q=0", "/search?q=1", "/other"),
        "https://example.com/search?q=0": page(),
        "https://example.com/search?q=1": page(),
        # ...and two more from a second page, reached only after the checkpoint below.
        "https://example.com/other": page("/search?q=2", "/search?q=3"),
        "https://example.com/search?q=2": page(),
        "https://example.com/search?q=3": page(),
    }

    def search_urls(result):
        return sorted(p.url for p in result.pages if p.url.startswith("https://example.com/search"))

    full = crawl_site(
        "https://example.com/",
        fetcher=_fetcher(site),
        sleeper=lambda _s: None,
        min_delay=0,
        max_urls=50,
        max_query_variants_per_path=2,
        config_fingerprint="fp",
    )
    assert len(search_urls(full)) == 2
    assert full.excluded.get("query_variants_limit") == 2

    out_dir = tmp_path / "run"
    out_dir.mkdir()
    state_path = str(out_dir / "state.json")

    # Stopped right after the start page: /search?q=0 and /search?q=1 are already
    # enqueued (and the budget for that path already spent), /other is not yet fetched.
    part = crawl_site(
        "https://example.com/",
        fetcher=_fetcher(site),
        sleeper=lambda _s: None,
        min_delay=0,
        max_urls=1,
        state_path=state_path,
        max_query_variants_per_path=2,
        config_fingerprint="fp",
    )
    assert part.partial is True

    resumed = crawl_site(
        "https://example.com/",
        fetcher=_fetcher(site),
        sleeper=lambda _s: None,
        min_delay=0,
        max_urls=50,
        state_path=state_path,
        max_query_variants_per_path=2,
        config_fingerprint="fp",
    )
    assert resumed.resumed is True
    # Not 4: the budget for /search was already spent by the checkpointed run, and that
    # must still hold once /other's two more variants are discovered after the resume.
    assert search_urls(resumed) == search_urls(full)
    assert resumed.excluded.get("query_variants_limit") == 2


SITE_WITH_RICH_LINKS = {
    "https://example.com/robots.txt": FakeResponse(
        ROBOTS_OK, headers={"content-type": "text/plain"}
    ),
    "https://example.com/": FakeResponse(
        "<html><head><title>t</title></head><body><h1>t</h1>"
        '<a href="/a" rel="nofollow noopener" target="_blank">a</a>'
        '<a href="/b">b</a>'
        "</body></html>"
    ),
    "https://example.com/a": page(),
    "https://example.com/b": page(),
}


def test_a_resumed_crawl_keeps_link_rel_as_a_tuple(tmp_path):
    """Captured link attributes survive the checkpoint sidecar with the type they had in
    memory. ``rel`` is a tuple on a fresh crawl; JSON only has lists, so without coercion on
    the way back a resumed crawl would hand callers ['nofollow'] where an uninterrupted one
    hands ('nofollow',) -- and every ``rel == ("nofollow",)`` comparison downstream would
    quietly stop matching on exactly the crawls that had to be resumed."""
    out_dir = tmp_path / "run"
    out_dir.mkdir()
    state_path = str(out_dir / "state.json")
    links_path = str(out_dir / "links.jsonl")

    part = crawl_site(
        "https://example.com/",
        fetcher=_fetcher(SITE_WITH_RICH_LINKS),
        sleeper=lambda _s: None,
        min_delay=0,
        max_urls=1,
        state_path=state_path,
        links_path=links_path,
        capture_link_attributes=True,
        config_fingerprint="fp",
    )
    assert part.partial is True

    resumed = crawl_site(
        "https://example.com/",
        fetcher=_fetcher(SITE_WITH_RICH_LINKS),
        sleeper=lambda _s: None,
        min_delay=0,
        max_urls=50,
        state_path=state_path,
        links_path=links_path,
        capture_link_attributes=True,
        config_fingerprint="fp",
    )
    assert resumed.resumed is True

    replayed = [e for e in resumed.links if e.destination.endswith("/a")]
    assert replayed, "the edge recorded before the checkpoint must survive the resume"
    for edge in replayed:
        assert isinstance(edge.rel, tuple)
        assert edge.rel == ("nofollow", "noopener")
        assert edge.target == "_blank"
