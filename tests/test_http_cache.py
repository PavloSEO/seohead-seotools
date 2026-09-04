"""HTTP response cache: freshness policy, Vary, revalidation, safety. No network.

The freshness policy is the point of #16, so it is tested directly against
``freshness_lifetime`` and ``ResponseCache.decide`` rather than only through a full crawl —
this is what lets "stale vs fresh" and "revalidate vs miss" be asserted precisely.
"""

from __future__ import annotations

import os
import pickle
from concurrent.futures import ThreadPoolExecutor

from seohead.crawl import cache as http_cache
from seohead.crawl.cache import CacheEntry, ResponseCache, freshness_lifetime

# ── freshness_lifetime: the stated policy, directly ─────────────────────────


def test_no_store_means_never_cached():
    _max_age, no_store = freshness_lifetime({"cache-control": "no-store"})
    assert no_store is True


def test_no_cache_means_stored_but_immediately_stale():
    max_age, no_store = freshness_lifetime({"cache-control": "no-cache"})
    assert no_store is False
    assert max_age == 0.0


def test_max_age_sets_the_freshness_window():
    max_age, no_store = freshness_lifetime({"cache-control": "max-age=120"})
    assert no_store is False
    assert max_age == 120.0


def test_expires_is_computed_against_date():
    headers = {
        "date": "Wed, 01 Jan 2025 00:00:00 GMT",
        "expires": "Wed, 01 Jan 2025 00:05:00 GMT",
    }
    max_age, _no_store = freshness_lifetime(headers)
    assert max_age == 300.0


def test_no_freshness_information_at_all_is_treated_as_already_stale():
    """The stated, conservative default: "unstated" is not "forever"."""
    max_age, no_store = freshness_lifetime({})
    assert no_store is False
    assert max_age == 0.0


def test_max_age_wins_over_expires_when_both_are_present():
    headers = {
        "cache-control": "max-age=10",
        "date": "Wed, 01 Jan 2025 00:00:00 GMT",
        "expires": "Wed, 01 Jan 2025 01:00:00 GMT",
    }
    max_age, _ = freshness_lifetime(headers)
    assert max_age == 10.0


# ── decide(): hit, revalidate, miss ─────────────────────────────────────────


def test_a_repeated_fetch_inside_the_freshness_window_is_a_hit(tmp_path):
    cache = ResponseCache(tmp_path)
    cache.store(
        "https://example.com/",
        {"User-Agent": "seohead"},
        200,
        {"cache-control": "max-age=3600"},
        "<html>fresh</html>",
    )
    outcome = cache.decide("https://example.com/", {"User-Agent": "seohead"})
    assert outcome.status == "hit"
    assert outcome.entry.body == "<html>fresh</html>"
    assert cache.stats["hits"] == 1


def test_an_expired_entry_with_a_validator_revalidates_not_a_fresh_fetch(tmp_path):
    cache = ResponseCache(tmp_path)
    cache.store(
        "https://example.com/",
        {"User-Agent": "seohead"},
        200,
        {"cache-control": "max-age=0", "etag": '"abc123"'},
        "<html>old</html>",
    )
    outcome = cache.decide("https://example.com/", {"User-Agent": "seohead"})
    assert outcome.status == "revalidate"
    assert outcome.conditional_headers["If-None-Match"] == '"abc123"'

    # A 304 confirms the body: recorded as a revalidation, never as a fresh fetch (only the
    # initial store() call above should ever count as a store).
    cache.refresh(outcome.entry, {"cache-control": "max-age=3600"})
    assert cache.stats["revalidations"] == 1
    assert cache.stats["stores"] == 1
    refreshed = cache.decide("https://example.com/", {"User-Agent": "seohead"})
    assert refreshed.status == "hit"
    assert refreshed.entry.body == "<html>old</html>"


def test_an_expired_entry_with_no_validator_is_a_plain_miss(tmp_path):
    cache = ResponseCache(tmp_path)
    cache.store(
        "https://example.com/", {"User-Agent": "seohead"}, 200, {"cache-control": "max-age=0"}, "x"
    )
    outcome = cache.decide("https://example.com/", {"User-Agent": "seohead"})
    assert outcome.status == "miss"


def test_a_cold_url_is_a_miss(tmp_path):
    cache = ResponseCache(tmp_path)
    outcome = cache.decide("https://example.com/never-seen", {"User-Agent": "seohead"})
    assert outcome.status == "miss"


def test_no_store_response_is_never_written(tmp_path):
    cache = ResponseCache(tmp_path)
    cache.store(
        "https://example.com/", {"User-Agent": "seohead"}, 200, {"cache-control": "no-store"}, "x"
    )
    assert cache.decide("https://example.com/", {"User-Agent": "seohead"}).status == "miss"
    assert cache.stats["bypassed"] == 1


def test_a_5xx_response_is_never_stored(tmp_path):
    cache = ResponseCache(tmp_path)
    cache.store(
        "https://example.com/", {"User-Agent": "seohead"}, 503, {"cache-control": "max-age=60"}, "x"
    )
    assert cache.decide("https://example.com/", {"User-Agent": "seohead"}).status == "miss"


# ── Vary ─────────────────────────────────────────────────────────────────────


def test_two_requests_differing_only_in_a_vary_listed_header_do_not_share_an_entry(tmp_path):
    cache = ResponseCache(tmp_path)
    cache.store(
        "https://example.com/",
        {"User-Agent": "desktop-ua"},
        200,
        {"cache-control": "max-age=3600", "vary": "User-Agent"},
        "<html>desktop</html>",
    )
    same_variant = cache.decide("https://example.com/", {"User-Agent": "desktop-ua"})
    other_variant = cache.decide("https://example.com/", {"User-Agent": "mobile-ua"})
    assert same_variant.status == "hit"
    assert other_variant.status == "miss"


def test_vary_star_is_never_cached(tmp_path):
    cache = ResponseCache(tmp_path)
    cache.store(
        "https://example.com/",
        {"User-Agent": "x"},
        200,
        {"cache-control": "max-age=60", "vary": "*"},
        "x",
    )
    assert cache.stats["bypassed"] == 1
    assert cache.stats["stores"] == 0
    assert cache.decide("https://example.com/", {"User-Agent": "x"}).status == "miss"


def test_two_variants_of_the_same_url_can_both_be_stored(tmp_path):
    cache = ResponseCache(tmp_path)
    for ua, body in (("desktop-ua", "desktop"), ("mobile-ua", "mobile")):
        cache.store(
            "https://example.com/",
            {"User-Agent": ua},
            200,
            {"cache-control": "max-age=3600", "vary": "User-Agent"},
            body,
        )
    desktop = cache.decide("https://example.com/", {"User-Agent": "desktop-ua"})
    mobile = cache.decide("https://example.com/", {"User-Agent": "mobile-ua"})
    assert desktop.entry.body == "desktop"
    assert mobile.entry.body == "mobile"


# ── replay mode and explicit invalidation ───────────────────────────────────


def test_replay_mode_serves_a_stale_entry_without_revalidating(tmp_path):
    cache = ResponseCache(tmp_path, mode="replay")
    cache.store(
        "https://example.com/",
        {"User-Agent": "x"},
        200,
        {"cache-control": "max-age=0"},
        "stale body",
    )
    outcome = cache.decide("https://example.com/", {"User-Agent": "x"})
    assert outcome.status == "hit"
    assert outcome.entry.body == "stale body"


def test_replay_mode_still_fetches_live_for_a_url_it_has_never_seen(tmp_path):
    cache = ResponseCache(tmp_path, mode="replay")
    assert cache.decide("https://example.com/new", {"User-Agent": "x"}).status == "miss"


def test_invalidate_forces_a_miss_but_still_allows_a_fresh_store(tmp_path):
    cache = ResponseCache(tmp_path, invalidate=True)
    cache.store(
        "https://example.com/",
        {"User-Agent": "x"},
        200,
        {"cache-control": "max-age=3600"},
        "old",
    )
    outcome = cache.decide("https://example.com/", {"User-Agent": "x"})
    assert outcome.status == "miss"
    assert cache.stats["invalidated"] == 1
    cache.store(
        "https://example.com/",
        {"User-Agent": "x"},
        200,
        {"cache-control": "max-age=3600"},
        "new",
    )
    # A later, non-invalidating cache pointed at the same directory sees the refreshed entry.
    plain = ResponseCache(tmp_path)
    assert plain.decide("https://example.com/", {"User-Agent": "x"}).entry.body == "new"


def test_off_mode_never_reads_or_writes(tmp_path):
    cache = ResponseCache(tmp_path, mode="off")
    cache.store(
        "https://example.com/", {"User-Agent": "x"}, 200, {"cache-control": "max-age=3600"}, "x"
    )
    assert cache.decide("https://example.com/", {"User-Agent": "x"}).status == "bypass"
    assert not os.listdir(tmp_path)


def test_build_returns_none_for_off_mode_or_no_directory():
    assert http_cache.build(None) is None
    assert http_cache.build("/tmp/whatever", mode="off") is None


# ── safety: a hostile or corrupt entry is a miss, never a crash ─────────────


def test_a_hostile_entry_file_cannot_execute_code_and_is_treated_as_a_miss(tmp_path):
    cache = ResponseCache(tmp_path)
    entry = CacheEntry(url="https://example.com/", stored_at=0, max_age=3600)
    path = cache._entry_path(entry)
    path.parent.mkdir(parents=True, exist_ok=True)

    marker = tmp_path / "pwned"

    class Payload:
        def __reduce__(self):
            return (os.system, (f"touch {marker}",))

    path.write_bytes(pickle.dumps(Payload()))

    outcome = cache.decide("https://example.com/", {})
    assert outcome.status == "miss"
    assert not marker.exists()


def test_a_truncated_entry_file_is_ignored_not_raised(tmp_path):
    cache = ResponseCache(tmp_path)
    entry = CacheEntry(url="https://example.com/", stored_at=0, max_age=3600)
    path = cache._entry_path(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"schema_version": ')
    assert cache.decide("https://example.com/", {}).status == "miss"


def test_a_world_writable_cache_directory_disables_the_cache_not_the_run(tmp_path):
    directory = tmp_path / "cache"
    directory.mkdir()
    os.chmod(directory, 0o777)
    cache = ResponseCache(directory)
    # Disabled, not raising: a broken cache degrades to "no cache".
    assert cache.decide("https://example.com/", {}).status == "bypass"
    cache.store("https://example.com/", {}, 200, {"cache-control": "max-age=60"}, "x")  # no crash


# ── concurrency: many threads, same and different URLs, no corruption ──────


def test_concurrent_stores_and_lookups_do_not_corrupt_the_cache_or_lose_stats(tmp_path):
    cache = ResponseCache(tmp_path)
    urls = [f"https://example.com/{i % 5}" for i in range(200)]  # heavy overlap on 5 keys

    def worker(i: int) -> str:
        url = urls[i]
        cache.store(
            url, {"User-Agent": "x"}, 200, {"cache-control": "max-age=3600"}, f"body-{i % 5}"
        )
        return cache.decide(url, {"User-Agent": "x"}).status

    with ThreadPoolExecutor(max_workers=16) as pool:
        statuses = list(pool.map(worker, range(200)))

    assert set(statuses) <= {"hit"}
    assert cache.stats["stores"] == 200
    # Every family directory still holds exactly one readable, valid variant.
    for i in range(5):
        outcome = cache.decide(f"https://example.com/{i}", {"User-Agent": "x"})
        assert outcome.status == "hit"
        assert outcome.entry.body == f"body-{i}"
