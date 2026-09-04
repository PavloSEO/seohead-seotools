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
