"""Level-batched concurrent fetching (#25): faster, still deterministic, still polite.

Every test here is network-free. Latency is simulated with real (small) sleeps
in an injected fetcher, never with an actual socket, so these are regression
tests for the scheduling and throttling logic itself.

Concurrency was reimplemented on top of resumable crawls, the wall-clock
budget, and KeyboardInterrupt handling — all added to ``crawl_site`` after the
original concurrency branch was cut — so a second group of tests below checks
that those features still hold with more than one worker in flight: per-hop
credentials, a checkpoint saved from a complete frontier rather than mid-batch
state, interrupt-safe requeuing, and the duration budget.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from itertools import pairwise

import pytest

from seohead.crawl.spider import crawl_site
from seohead.crawl.throttle import Throttle
from tests.test_crawl_spider import SITE, FakeResponse, _fetcher, page


def _pages_without_timing(pages) -> list[dict]:
    """Every recorded field except response_time, which legitimately varies."""
    out = []
    for record in pages:
        data = asdict(record)
        data.pop("response_time", None)
        out.append(data)
    return out


def _fanned_out_site(n: int, target_factory=page) -> tuple[dict, list[str]]:
    """A root page linking to ``n`` distinct leaves, one BFS level deep."""
    leaves = [f"/leaf{i}" for i in range(n)]
    site = {
        "https://example.com/robots.txt": FakeResponse(
            "User-agent: *\n", headers={"content-type": "text/plain"}
        ),
        "https://example.com/": target_factory(*leaves),
    }
    for leaf in leaves:
        site[f"https://example.com{leaf}"] = page()
    return site, leaves


# --- determinism: concurrency changes speed, never the recorded output -----


def test_output_is_byte_identical_at_any_concurrency():
    """The acceptance test from #25: same pages.jsonl at concurrency 1 or 8."""
    sequential = crawl_site(
        "https://example.com/", fetcher=_fetcher(SITE), sleeper=lambda _s: None, min_delay=0
    )
    concurrent = crawl_site(
        "https://example.com/",
        fetcher=_fetcher(SITE),
        sleeper=lambda _s: None,
        min_delay=0,
        concurrency=8,
    )
    assert [p.url for p in concurrent.pages] == [p.url for p in sequential.pages]
    assert _pages_without_timing(concurrent.pages) == _pages_without_timing(sequential.pages)
    assert concurrent.links == sequential.links
    assert concurrent.excluded == sequential.excluded
    assert concurrent.max_depth_reached == sequential.max_depth_reached


def test_a_wide_fan_out_is_still_recorded_in_queue_order_under_concurrency():
    """pool.map hands results back in submission order, not completion order —
    this is what makes a concurrent crawl's output reproducible at all."""
    site, leaves = _fanned_out_site(20)
    result = crawl_site(
        "https://example.com/",
        fetcher=_fetcher(site),
        sleeper=lambda _s: None,
        min_delay=0,
        concurrency=8,
        max_urls=50,
    )
    expected = ["https://example.com/"] + [f"https://example.com{leaf}" for leaf in leaves]
    assert [p.url for p in result.pages] == expected


def test_traversal_is_deterministic_across_concurrent_runs():
    site, _ = _fanned_out_site(15)
    first = [
        p.url
        for p in crawl_site(
            "https://example.com/",
            fetcher=_fetcher(site),
            sleeper=lambda _s: None,
            min_delay=0,
            concurrency=6,
        ).pages
    ]
    second = [
        p.url
        for p in crawl_site(
            "https://example.com/",
            fetcher=_fetcher(site),
            sleeper=lambda _s: None,
            min_delay=0,
            concurrency=6,
        ).pages
    ]
    assert first == second


# --- throughput: overlapping wait time is the whole point ------------------


def _slow_fetcher(mapping: dict, latency: float):
    def fetch(url: str):
        time.sleep(latency)
        value = mapping.get(url)
        if value is None:
            return FakeResponse("", status_code=404)
        return value

    return fetch


def test_wall_clock_drops_with_concurrency_up_to_the_cap():
    """A fixture with simulated per-request latency should crawl noticeably
    faster at concurrency 4 than sequentially — the throughput half of #25."""
    site, _ = _fanned_out_site(16)
    latency = 0.03

    started = time.monotonic()
    crawl_site(
        "https://example.com/",
        fetcher=_slow_fetcher(site, latency),
        min_delay=0,
        max_urls=50,
        concurrency=1,
    )
    sequential_elapsed = time.monotonic() - started

    started = time.monotonic()
    crawl_site(
        "https://example.com/",
        fetcher=_slow_fetcher(site, latency),
        min_delay=0,
        max_urls=50,
        concurrency=4,
    )
    concurrent_elapsed = time.monotonic() - started

    # Generous margin against CI scheduling noise: a purely sequential
    # implementation would show no improvement at all (ratio ~= 1.0).
    assert concurrent_elapsed < sequential_elapsed * 0.7


# --- politeness: the floor is shared, not multiplied by the worker count ---


def test_min_delay_paces_dispatch_across_workers_not_per_worker():
    """N concurrent workers must not turn one floor into N times the rate.

    Real (small) sleeps are used so actual dispatch timestamps are meaningful;
    the assertion is a lower bound, so it cannot flake toward false failure.
    """
    site, leaves = _fanned_out_site(6)
    delay = 0.03
    dispatch_times: list[float] = []
    leaf_urls = {f"https://example.com{leaf}" for leaf in leaves}

    def fetch(url: str):
        if url in leaf_urls:
            dispatch_times.append(time.monotonic())
        value = site.get(url)
        return value if value is not None else FakeResponse("", status_code=404)

    crawl_site(
        "https://example.com/",
        fetcher=fetch,
        min_delay=delay,
        max_urls=50,
        concurrency=4,
    )

    assert len(dispatch_times) == len(leaves)
    gaps = [b - a for a, b in pairwise(dispatch_times)]
    # Each gap must respect the floor; a per-worker-independent sleep would
    # let several of these collapse toward zero instead.
    assert all(gap >= delay * 0.8 for gap in gaps), gaps


# --- circuit breaker: the shared signal still stops the crawl --------------


def test_repeated_timeouts_stop_a_concurrent_crawl_before_the_queue_drains():
    targets = [f"/p{i}" for i in range(12)]
    site = {
        "https://example.com/robots.txt": FakeResponse(
            "User-agent: *\n", headers={"content-type": "text/plain"}
        ),
        "https://example.com/": page(*targets),
    }
    for path in targets:
        site[f"https://example.com{path}"] = TimeoutError("read timed out")

    result = crawl_site(
        "https://example.com/",
        fetcher=_fetcher(site),
        sleeper=lambda _s: None,
        min_delay=0,
        max_urls=50,
        concurrency=4,
    )
    assert result.partial is True
    assert "timeouts" in result.stopped_reason
    assert len(result.pages) < len(targets) + 1, "must stop before exhausting the queue"


def test_repeated_server_refusals_stop_a_concurrent_crawl():
    targets = [f"/p{i}" for i in range(12)]
    site = {
        "https://example.com/robots.txt": FakeResponse(
            "User-agent: *\n", headers={"content-type": "text/plain"}
        ),
        "https://example.com/": page(*targets),
    }
    for path in targets:
        site[f"https://example.com{path}"] = FakeResponse("", status_code=503)

    result = crawl_site(
        "https://example.com/",
        fetcher=_fetcher(site),
        sleeper=lambda _s: None,
        min_delay=0,
        max_urls=50,
        concurrency=4,
    )
    assert result.partial is True
    assert "refused repeatedly" in result.stopped_reason
    assert len(result.pages) < len(targets) + 1, "must stop before exhausting the queue"


def test_circuit_breaker_trip_point_is_stable_regardless_of_thread_scheduling():
    """A batch large enough that several workers can race record_timeout()
    simultaneously must still trip the breaker at the same record the
    sequential crawler would have stopped at — not wherever OS scheduling
    happened to land, and not a moving target across repeated runs.

    Real threads are used deliberately, over many repeats: the bug this
    guards against (reading Throttle's live, worker-mutated streak instead of
    a queue-ordered replay) is invisible with a small batch, since 2 or 3
    racing failures still stay under the trip threshold either way.
    """
    good = [f"/good{i}" for i in range(20)]
    bad = [f"/bad{i}" for i in range(8)]
    site = {
        "https://example.com/robots.txt": FakeResponse(
            "User-agent: *\n", headers={"content-type": "text/plain"}
        ),
        "https://example.com/": page(*(good + bad)),
    }
    for g in good:
        site[f"https://example.com{g}"] = page()
    for b in bad:
        site[f"https://example.com{b}"] = TimeoutError("read timed out")

    baseline = None
    for _ in range(10):
        result = crawl_site(
            "https://example.com/",
            fetcher=_fetcher(site),
            sleeper=lambda _s: None,
            min_delay=0,
            max_urls=100,
            concurrency=8,
        )
        assert result.finish_reason == "errors"
        bad_fetched = [p.url for p in result.pages if "/bad" in p.url]
        # Exactly the streak length the sequential crawler would record: the
        # first 5 bad targets in queue order, never more, never fewer.
        assert bad_fetched == [f"https://example.com/bad{i}" for i in range(5)]
        if baseline is None:
            baseline = len(result.pages)
        else:
            assert len(result.pages) == baseline


def test_the_url_budget_is_exact_under_concurrency():
    site, _ = _fanned_out_site(20)
    result = crawl_site(
        "https://example.com/",
        fetcher=_fetcher(site),
        sleeper=lambda _s: None,
        min_delay=0,
        concurrency=8,
        max_urls=5,
    )
    assert len(result.pages) == 5
    assert result.partial is True
    assert "url limit" in result.stopped_reason


# --- adaptive concurrency lives on Throttle ---------------------------------


def test_concurrency_starts_conservative_not_at_the_ceiling():
    t = Throttle(max_concurrency=4)
    assert 1 < t.concurrency < 4


def test_concurrency_widens_only_after_sustained_success():
    t = Throttle(max_concurrency=4)
    start = t.concurrency
    t.record_response(0.01, ok=True)
    assert t.concurrency == start, "one good response must not be enough on its own"
    for _ in range(20):
        t.record_response(0.01, ok=True)
    assert t.concurrency == 4, "sustained success should reach the configured ceiling"


def test_a_timeout_collapses_concurrency_back_to_one():
    t = Throttle(max_concurrency=4)
    for _ in range(20):
        t.record_response(0.01, ok=True)
    assert t.concurrency > 1
    t.record_timeout()
    assert t.concurrency == 1


def test_a_server_error_collapses_concurrency_back_to_one():
    t = Throttle(max_concurrency=4)
    for _ in range(20):
        t.record_response(0.01, ok=True)
    assert t.concurrency > 1
    t.record_server_error(503)
    assert t.concurrency == 1


def test_a_single_worker_ceiling_behaves_exactly_like_today():
    """max_concurrency=1 (the default) must never widen, matching the crawler
    that existed before #25."""
    t = Throttle()
    for _ in range(50):
        t.record_response(0.01, ok=True)
    assert t.concurrency == 1


@pytest.mark.parametrize("bad_concurrency", [0, -1])
def test_concurrency_is_never_configured_below_one(bad_concurrency):
    t = Throttle(max_concurrency=bad_concurrency)
    assert t.max_concurrency == 1
    assert t.concurrency == 1


# --- composing with everything main gained after this branch was cut -------
#
# The concurrency branch predates resumable crawls, the wall-clock budget, and
# KeyboardInterrupt handling. Each of those must still hold with more than one
# request in flight — these tests are the acceptance criteria for that.


def test_credentials_are_still_resolved_per_hop_under_concurrency(monkeypatch):
    """A stale host from another worker's hop must never decide this URL's
    headers — the per-hop guarantee must survive concurrent dispatch."""
    import seohead.crawl.spider as spider_mod

    seen_hosts: list[str] = []
    monkeypatch.setattr(
        spider_mod,
        "resolve_credential_headers",
        lambda entries, host: seen_hosts.append(host) or {},
    )
    site, leaves = _fanned_out_site(10)
    crawl_site(
        "https://example.com/",
        fetcher=_fetcher(site),
        sleeper=lambda _s: None,
        min_delay=0,
        concurrency=4,
        credential_headers=[{"host": "example.com", "headers": {}}],
    )
    # One resolution per fetch (root + every leaf), every one for this host —
    # order is not guaranteed once several workers resolve concurrently, but
    # every single resolution must still be for the URL's own host.
    assert len(seen_hosts) == 1 + len(leaves)
    assert set(seen_hosts) == {"example.com"}


def test_a_circuit_breaker_trip_mid_batch_checkpoints_the_untouched_tail(tmp_path):
    """When the breaker trips partway through a batch, the URLs after the
    tripping one in queue order must still be on the saved frontier — the
    checkpoint must reflect a consistent frontier, not mid-batch state."""
    targets = [f"/p{i}" for i in range(8)]
    site = {
        "https://example.com/robots.txt": FakeResponse(
            "User-agent: *\n", headers={"content-type": "text/plain"}
        ),
        "https://example.com/": page(*targets),
    }
    for path in targets:
        site[f"https://example.com{path}"] = TimeoutError("read timed out")

    state_path = str(tmp_path / "state.json")
    result = crawl_site(
        "https://example.com/",
        fetcher=_fetcher(site),
        sleeper=lambda _s: None,
        min_delay=0,
        max_urls=50,
        concurrency=4,
        state_path=state_path,
    )
    assert result.finish_reason == "errors"

    with open(state_path, encoding="utf-8") as fh:
        saved = json.load(fh)
    queued = {u for u, _d in saved["queue"]}
    fetched = {p.url for p in result.pages}
    all_targets = {f"https://example.com{p}" for p in targets}
    # Every target URL is either recorded as fetched or still on the
    # checkpointed frontier — none may have vanished from both.
    assert fetched | queued >= all_targets
    assert not (fetched & queued), "a URL cannot be both fetched and still queued"


def test_a_keyboard_interrupt_mid_batch_requeues_the_unprocessed_tail(tmp_path):
    """The interrupted URL, and anything after it in the same batch that this
    run never confirmed as processed, must survive to resume."""
    targets = [f"/p{i}" for i in range(6)]
    site = {
        "https://example.com/robots.txt": FakeResponse(
            "User-agent: *\n", headers={"content-type": "text/plain"}
        ),
        "https://example.com/": page(*targets),
    }
    for path in targets:
        site[f"https://example.com{path}"] = page()

    def fetch(url):
        if url == "https://example.com/p1":
            raise KeyboardInterrupt
        return site.get(url, FakeResponse("", status_code=404))

    state_path = str(tmp_path / "state.json")
    result = crawl_site(
        "https://example.com/",
        fetcher=fetch,
        sleeper=lambda _s: None,
        min_delay=0,
        max_urls=50,
        concurrency=4,
        state_path=state_path,
    )
    assert result.finish_reason == "interrupted"
    assert result.partial is True

    with open(state_path, encoding="utf-8") as fh:
        saved = json.load(fh)
    queued = {u for u, _d in saved["queue"]}
    assert "https://example.com/p1" in queued, "the interrupted URL must be retried on resume"


def test_max_seconds_still_ends_a_concurrent_crawl_with_a_duration_finish_reason():
    site, _ = _fanned_out_site(30)
    ticking = {"t": 0.0}

    def fake_clock():
        ticking["t"] += 2  # each check sees two seconds pass
        return ticking["t"]

    result = crawl_site(
        "https://example.com/",
        fetcher=_fetcher(site),
        sleeper=lambda _s: None,
        min_delay=0,
        max_urls=100,
        max_seconds=5,
        clock=fake_clock,
        concurrency=4,
    )
    assert result.finish_reason == "duration_limit"
    assert result.partial is True
    assert len(result.pages) < 31, "must stop well before exhausting the site"


def test_resuming_a_concurrent_crawl_does_not_refetch_completed_urls(tmp_path):
    site, leaves = _fanned_out_site(6)
    state_path = str(tmp_path / "state.json")
    out_path = str(tmp_path / "pages.jsonl")

    first = crawl_site(
        "https://example.com/",
        fetcher=_fetcher(site),
        sleeper=lambda _s: None,
        min_delay=0,
        max_urls=1,
        state_path=state_path,
        out_path=out_path,
        concurrency=4,
    )
    assert {p.url for p in first.pages} == {"https://example.com/"}

    hits: list[str] = []

    def fetch(url):
        hits.append(url)
        return site.get(url, FakeResponse("", status_code=404))

    second = crawl_site(
        "https://example.com/",
        fetcher=fetch,
        sleeper=lambda _s: None,
        min_delay=0,
        max_urls=50,
        state_path=state_path,
        out_path=out_path,
        concurrency=4,
    )
    assert second.resumed is True
    assert "https://example.com/" not in hits
    expected_leaves = {f"https://example.com{leaf}" for leaf in leaves}
    assert set(hits) == {"https://example.com/robots.txt"} | expected_leaves
    assert {p.url for p in second.pages} == {"https://example.com/"} | expected_leaves
    assert second.finish_reason == "finished"
