"""Breadth-first link discovery — the part that makes this a crawler.

Fetching a list someone else produced tests the fetcher. Following links is the
thing that closes the gap: without it the toolkit cannot obtain a URL list of
its own, which is the whole reason this module exists.

Traversal is deterministic given identical responses: the frontier is a queue,
children are enqueued in document order rather than sorted, and every exclusion
is recorded as data rather than dropped silently. That guarantee survives
concurrency too — a slice of the frontier is fetched as a batch of concurrent
requests, but results are always folded back in the order they were queued —
into ``result.pages``, the circuit breaker, redirect and link enqueueing, and
the checkpoint — before anything downstream sees them, so the recorded output
does not depend on which request happened to answer first.
"""

from __future__ import annotations

import contextlib
import dataclasses
import json
import os
import re
import threading
import time
from collections import deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from seohead.crawl import state as crawl_state
from seohead.crawl.collect import CrawlResult, PageRecord, _is_timeout, _write, fetch_one
from seohead.crawl.settings import resolve_credential_headers
from seohead.crawl.throttle import Throttle
from seohead.recon.net import http_client, normalize_url, registrable_domain
from seohead.tools.robots import crawl_delay, is_allowed, match_path, parse_robots

MAX_URLS_CEILING = 10_000
MAX_DEPTH_CEILING = 20
# A ceiling on the *configured* value, not on what the adaptive throttle will
# actually use — Throttle.concurrency starts low and earns its way up to
# whichever of this or the caller's request is smaller.
MAX_CONCURRENCY_CEILING = 16
ROBOTS_TOKEN = "SEOHEAD-Tools"
EMPTY_ROBOTS = {"allow": [], "disallow": [], "groups": [], "crawl_delay": None}
# Matches Throttle.should_stop / host_is_failing's own default limit — kept as
# a separate constant here because the circuit breaker's *decision* is no
# longer read off Throttle's live counters (see _fold_failure_streaks below).
STOP_AFTER_CONSECUTIVE_FAILURES = 5


class _DispatchGate:
    """Spaces out request *dispatch* across every concurrent worker sharing one
    origin, so ``min_delay`` still means "at least this long between requests
    to the origin" once more than one worker is fetching for it.

    Each worker independently sleeping ``throttle.delay`` before its own
    request would honour the floor against its own clock only: with N workers
    doing that in parallel, N requests would go out every ``delay`` seconds
    instead of one, multiplying the configured rate by N. This gate hands out
    dispatch turns from a single shared clock instead, so the gap between any
    two dispatches to the origin is still at least ``delay`` — concurrency then
    buys overlap on the response *wait*, never on how densely requests are sent.
    """

    def __init__(self, throttle: Throttle, sleeper: Callable[[float], None]) -> None:
        self._throttle = throttle
        self._sleeper = sleeper
        self._lock = threading.Lock()
        self._next_at = time.monotonic()

    def wait_turn(self) -> None:
        with self._lock:
            now = time.monotonic()
            start_at = max(now, self._next_at)
            self._next_at = start_at + self._throttle.delay
            wait = start_at - now
        if wait > 0:
            self._sleeper(wait)


@dataclass
class LinkEdge:
    source: str
    destination: str
    anchor: str
    nofollow: bool


@dataclass
class SpiderResult(CrawlResult):
    links: list[LinkEdge] = field(default_factory=list)
    excluded: dict[str, int] = field(default_factory=dict)
    max_depth_reached: int = 0
    robots_note: str = ""
    # URLs robots.txt disallows. Under "report_only" they are crawled anyway and
    # listed here, which is what an audit needs: full coverage plus an inventory
    # of what a compliant crawler would not have seen.
    robots_blocked: list[str] = field(default_factory=list)
    crawl_delay_applied: float | None = None
    effective_delay: float = 0.0
    # The adaptive concurrency level reached by the end of the crawl. 1 means
    # the crawl never ran more than one request in flight at a time, whether
    # because it was configured that way or because the origin never earned
    # more.
    effective_concurrency: int = 1
    # Why the checkpoint was or wasn't used, for the run output — see state.py.
    resume_note: str = ""
    # Seed URLs accepted into the frontier beyond the start URL itself (e.g. a
    # sitemap's declared URL set). Recorded so a sitemap-seeded run is
    # auditable: which URLs were fetched only because they were seeded, versus
    # discovered by following a link.
    seed_urls: list[str] = field(default_factory=list)


def _canonical_key(url: str) -> str:
    """Identity for de-duplication: fragment dropped, nothing else rewritten."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))


def _same_host(url: str, host: str) -> bool:
    return (urlsplit(url).hostname or "").lower() == host


def _fold_failure_streaks(
    record: PageRecord, consecutive_timeouts: int, consecutive_server_errors: int
) -> tuple[int, int]:
    """Advance the two failure streaks by exactly one record, in queue order.

    Mirrors Throttle.record_timeout / record_server_error / record_success —
    the same rules, applied to the *sequence of folded-back records* instead
    of Throttle's live counters. Those counters are mutated inside worker
    threads as each fetch actually completes, which is completion order, not
    queue order; reading them straight from ``after_fetch`` would make the
    circuit breaker's trip point depend on real thread scheduling instead of
    on the deterministic order the rest of the fold-back already uses. A
    non-timeout exception (``status_code`` never set, error not timeout-shaped)
    leaves both streaks untouched, matching ``fetch_one``: it calls none of
    Throttle's mutators in that case either.
    """
    if record.status_code is None:
        return (
            (consecutive_timeouts + 1, consecutive_server_errors)
            if _is_timeout(record.error)
            else (consecutive_timeouts, consecutive_server_errors)
        )
    if record.status_code == 429 or 500 <= record.status_code < 600:
        return consecutive_timeouts, consecutive_server_errors + 1
    return 0, 0


_PAGE_RECORD_FIELDS = {f.name for f in dataclasses.fields(PageRecord)}


def _read_pages_jsonl(path: str) -> list[PageRecord]:
    """Reconstruct previously fetched pages from a prior run's output.

    Unknown keys are dropped rather than rejected, so a state file written by
    an older build with fewer fields still resumes.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.readlines()
    except FileNotFoundError:
        return []
    pages = []
    for line in lines:
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except ValueError:
            continue  # a truncated final line must not discard the rest
        if isinstance(raw, dict):
            pages.append(PageRecord(**{k: v for k, v in raw.items() if k in _PAGE_RECORD_FIELDS}))
    return pages


@dataclass(frozen=True)
class Scope:
    """Which discovered URLs a crawl may fetch.

    The seed is always fetched: a crawl whose own start URL is filtered out
    would report an empty site rather than a configuration mistake. Everything
    reached from it is tested here, and every rejection is counted in
    ``SpiderResult.excluded`` under the rule that rejected it.
    """

    internal: str = "host"
    include_patterns: tuple[re.Pattern[str], ...] = ()
    exclude_patterns: tuple[re.Pattern[str], ...] = ()
    exclude_hosts: frozenset[str] = frozenset()

    @classmethod
    def from_config(cls, scope: dict[str, Any] | None) -> Scope:
        scope = scope or {}
        return cls(
            internal=scope.get("internal", "host"),
            include_patterns=tuple(re.compile(p) for p in scope.get("include_patterns") or ()),
            exclude_patterns=tuple(re.compile(p) for p in scope.get("exclude_patterns") or ()),
            exclude_hosts=frozenset(
                host.lower().lstrip(".") for host in scope.get("exclude_hosts") or ()
            ),
        )

    def is_internal(self, url: str, start_host: str) -> bool:
        host = (urlsplit(url).hostname or "").lower()
        if not host:
            return False
        if self.internal == "registrable_domain":
            return registrable_domain(host) == registrable_domain(start_host)
        return host == start_host

    def rejection(self, url: str, start_host: str) -> str:
        """The rule that rejects this URL, or "" when it may be fetched."""
        if not self.is_internal(url, start_host):
            return "outside_host"
        host = (urlsplit(url).hostname or "").lower()
        if any(host == bad or host.endswith("." + bad) for bad in self.exclude_hosts):
            return "excluded_host"
        if any(pattern.search(url) for pattern in self.exclude_patterns):
            return "excluded_by_pattern"
        if self.include_patterns and not any(p.search(url) for p in self.include_patterns):
            return "not_included_by_pattern"
        return ""


def _fetch_robots(
    start: str, fetcher: Callable[[str], Any] | None, client: Any
) -> tuple[dict, str]:
    """Read robots.txt. A 5xx means stop, not "crawl allowed".

    RFC 9309 treats an unavailable robots.txt as a full disallow, and the
    practical reason is sharper than the standard: a host answering 5xx is
    already failing, and crawling it harder is the wrong response.
    """
    parts = urlsplit(start)
    robots_url = urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))
    try:
        response = fetcher(robots_url) if fetcher else client.get(robots_url)
    except Exception as exc:
        return {"allow": [], "disallow": [], "groups": []}, f"robots.txt unreachable: {exc}"
    code = getattr(response, "status_code", None)
    if code is not None and 500 <= code < 600:
        return {}, f"robots.txt returned {code}"
    if code is not None and code >= 400:
        return {"allow": [], "disallow": [], "groups": []}, "no robots.txt"
    return parse_robots(getattr(response, "text", "") or ""), ""


def crawl_site(
    start_url: str,
    *,
    max_urls: int = 200,
    max_depth: int = 5,
    max_seconds: float = 0,
    min_delay: float = 0.5,
    timeout: float = 15.0,
    robots_policy: str = "respect",
    scope: dict[str, Any] | Scope | None = None,
    seed_urls: list[str] | None = None,
    out_path: str | None = None,
    state_path: str | None = None,
    config_fingerprint: str = "",
    fetcher: Callable[[str], Any] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    credential_headers: list[dict[str, Any]] | None = None,
    clock: Callable[[], float] = time.monotonic,
    concurrency: int = 1,
) -> SpiderResult:
    """Crawl one host breadth-first from ``start_url``, within ``scope``.

    ``max_seconds`` is a wall-clock budget for the whole call; 0 means none.
    ``state_path``, when given, checkpoints the frontier there so a later call
    with the same path and start URL resumes instead of restarting —
    ``config_fingerprint`` is compared too, so a scope or limit change since the
    checkpoint starts fresh rather than mixing frontiers built under different
    rules.
    ``seed_urls``, when given, are additional entry points added to the
    frontier at depth 0 alongside ``start_url`` — a sitemap-seeded crawl mode:
    every declared URL is fetched and its own links are followed, rather than
    treating the sitemap as the final answer. Each seed still goes through
    ``scope`` like any discovered link, and a rejected seed is counted in
    ``excluded`` under the rule that rejected it. Being seeded is not being
    "found by following links": a seed with no inbound edge in ``links`` is
    still reachable only because it was declared, which is what makes orphan
    detection against ``result.links`` honest even in this mode.

    ``concurrency`` is a per-origin ceiling, not a promise: the crawl starts at
    a conservative fan-out and the adaptive throttle widens it toward this
    ceiling only on sustained success, collapsing back to one request in flight
    on the first timeout or server refusal. A dispatch gate paces requests from
    a single shared clock regardless of how many workers are running, so
    ``min_delay`` still means "at least this long between requests to the
    origin" — concurrency only overlaps the *wait* for a response, never the
    rate at which requests go out. Each slice of the frontier is fetched as one
    batch, sized to what the origin has earned, and results are folded back in
    queue order — into ``result.pages``, the circuit breaker, redirect and link
    enqueueing, and the checkpoint — before anything downstream sees them, so
    the output (and the saved frontier, on an early stop) is identical to
    ``concurrency=1`` aside from ``response_time``.
    """
    start = normalize_url(start_url)
    host = (urlsplit(start).hostname or "").lower() if start else ""
    # normalize_url is lenient — it turns "not a url" into "https://not a url" —
    # so the host is checked here rather than trusted.
    if not start or not host or " " in host or "." not in host:
        raise ValueError(f"not a crawlable URL: {start_url!r}")
    rules = scope if isinstance(scope, Scope) else Scope.from_config(scope)
    limit = max(1, min(int(max_urls), MAX_URLS_CEILING))
    depth_limit = max(0, min(int(max_depth), MAX_DEPTH_CEILING))
    max_concurrency = max(1, min(int(concurrency), MAX_CONCURRENCY_CEILING))
    if state_path:
        crawl_state.ensure_safe_dir(os.path.dirname(os.path.abspath(state_path)) or ".")

    result = SpiderResult()
    throttle = Throttle(min_delay=min_delay, max_concurrency=max_concurrency)
    excluded: dict[str, int] = {}
    crawl_started = clock()

    def exclude(reason: str) -> None:
        excluded[reason] = excluded.get(reason, 0) + 1

    with contextlib.ExitStack() as stack:
        client = None
        if fetcher is None:
            # A crawler must observe redirects, not be moved by them. With
            # follow_redirects on, a 301 is recorded as a 200 carrying the
            # target's title and body, the Location is never seen, and redirect
            # auditing is impossible — the old and new URL become duplicates.
            client, _ = http_client(timeout, follow_redirects=False)
            stack.callback(client.close)

        enforce = robots_policy == "respect"
        if robots_policy == "ignore":
            # Not fetched at all, so there is nothing to report either.
            robots, note = dict(EMPTY_ROBOTS), "robots.txt not fetched (policy: ignore)"
        else:
            robots, note = _fetch_robots(start, fetcher, client)
        result.robots_note = note
        if enforce and not robots:
            result.partial = True
            result.stopped_reason = note or "robots.txt unavailable"
            result.finish_reason = "robots_unavailable"
            return result

        # A site asking to be crawled slowly is asking the crawler, not the
        # operator. The configured delay is a floor, never a ceiling on politeness.
        asked = crawl_delay(robots, ROBOTS_TOKEN) if robots else None
        if asked and asked > throttle.min_delay:
            throttle.min_delay = asked
            throttle.delay = max(throttle.delay, asked)
            result.crawl_delay_applied = asked

        loaded_state, resume_note = (
            crawl_state.load(state_path, start, config_fingerprint) if state_path else (None, "")
        )
        result.resume_note = resume_note
        result.resumed = loaded_state is not None

        handle = None
        if out_path:
            if loaded_state:
                # Prior pages already live on disk; append rather than replace,
                # and bring them back into this run's evidence.
                result.pages.extend(_read_pages_jsonl(out_path))
            mode = "a" if loaded_state else "w"
            handle = stack.enter_context(open(out_path, mode, encoding="utf-8"))

        if loaded_state:
            queue: deque[tuple[str, int]] = deque(loaded_state.queue)
            seen: set[str] = set(loaded_state.seen)
            result.max_depth_reached = loaded_state.max_depth_reached
        else:
            queue = deque([(start, 0)])
            seen = {_canonical_key(start)}

        for seed in seed_urls or []:
            seed = (seed or "").strip()
            if not seed:
                continue
            reason = rules.rejection(seed, host)
            if reason:
                exclude(reason)
                continue
            key = _canonical_key(seed)
            if key in seen:
                continue
            seen.add(key)
            queue.append((seed, 0))
            result.seed_urls.append(seed)

        # The circuit breaker's own streaks, advanced only here as records are
        # folded back in queue order — see _fold_failure_streaks.
        consecutive_timeouts = 0
        consecutive_server_errors = 0

        def _extra_headers_for(url: str) -> dict[str, str] | None:
            # Resolved for this hop's own host, never carried over from the
            # last one — that is what keeps a credential off a cross-host
            # redirect target. Called with each URL's own host regardless of
            # concurrency, so nothing is ever carried between hops or workers.
            if not credential_headers:
                return None
            return resolve_credential_headers(credential_headers, urlsplit(url).hostname or "")

        def robots_blocks(url: str) -> bool:
            """True when this URL must not be fetched under the current policy."""
            if robots and not is_allowed(robots, match_path(url), ROBOTS_TOKEN):
                result.robots_blocked.append(url)
                if enforce:
                    exclude("blocked_by_robots")
                    return True
            return False

        def handle_redirect(record: PageRecord, depth: int) -> None:
            # A redirect is a discovery too, and it stays inside the budget.
            if record.redirect_url and depth < depth_limit:
                target = record.redirect_url
                reason = rules.rejection(target, host)
                if reason:
                    exclude("redirect_off_host" if reason == "outside_host" else reason)
                else:
                    key = _canonical_key(target)
                    if key not in seen:
                        seen.add(key)
                        queue.append((target, depth + 1))

        def handle_links(parsed: dict[str, Any] | None, url: str, depth: int) -> None:
            if parsed is None:
                return
            if depth >= depth_limit:
                exclude("depth_limit")
                return
            # Document order, not sorted: a truncated crawl must sample the page
            # as the page is written, not alphabetically.
            for link in parsed.get("links") or []:
                href = (link.get("href") or "").strip()
                if not href:
                    continue
                result.links.append(
                    LinkEdge(
                        source=url,
                        destination=href,
                        anchor=(link.get("text") or "")[:200],
                        nofollow=bool(link.get("nofollow")),
                    )
                )
                reason = rules.rejection(href, host)
                if reason:
                    exclude(reason)
                    continue
                key = _canonical_key(href)
                if key in seen:
                    continue
                seen.add(key)
                queue.append((href, depth + 1))

        def after_fetch(
            url: str, depth: int, record: PageRecord, parsed: dict[str, Any] | None
        ) -> bool:
            """Bookkeeping shared by every fetched page. Returns True to stop the crawl."""
            nonlocal consecutive_timeouts, consecutive_server_errors
            record.crawl_depth = depth
            result.pages.append(record)
            _write(handle, record)

            consecutive_timeouts, consecutive_server_errors = _fold_failure_streaks(
                record, consecutive_timeouts, consecutive_server_errors
            )
            if consecutive_timeouts >= STOP_AFTER_CONSECUTIVE_FAILURES:
                result.partial = True
                result.stopped_reason = "origin stopped responding (repeated timeouts)"
                result.finish_reason = "errors"
                return True
            if consecutive_server_errors >= STOP_AFTER_CONSECUTIVE_FAILURES:
                # The host has refused repeatedly. Continuing would measure the
                # crawler rather than the site.
                result.partial = True
                result.stopped_reason = "origin refused repeatedly (429/5xx) — crawl stopped"
                result.finish_reason = "errors"
                return True

            handle_redirect(record, depth)
            handle_links(parsed, url, depth)
            return False

        stopped = False
        if max_concurrency <= 1:
            # The plain sequential path: one request, wait for the response,
            # then the next. Kept byte-for-byte separate from the batched path
            # below so the common case (the default) carries zero concurrency
            # overhead and zero risk of it changing behaviour.
            while queue and not stopped:
                if len(result.pages) >= limit:
                    result.partial = True
                    result.stopped_reason = f"url limit reached ({limit})"
                    result.finish_reason = "url_limit"
                    break
                if max_seconds and (clock() - crawl_started) >= max_seconds:
                    result.partial = True
                    result.stopped_reason = f"duration limit reached ({max_seconds:.0f}s)"
                    result.finish_reason = "duration_limit"
                    break
                url, depth = queue.popleft()
                result.max_depth_reached = max(result.max_depth_reached, depth)

                if robots_blocks(url):
                    continue

                try:
                    if throttle.delay:
                        sleeper(throttle.delay)
                    record, parsed = fetch_one(
                        url,
                        client=client,
                        fetcher=fetcher,
                        throttle=throttle,
                        extra_headers=_extra_headers_for(url),
                    )
                except KeyboardInterrupt:
                    # Not processed: put it back so a resume retries it rather
                    # than silently dropping it from the frontier.
                    queue.appendleft((url, depth))
                    result.partial = True
                    result.stopped_reason = "interrupted"
                    result.finish_reason = "interrupted"
                    break
                stopped = after_fetch(url, depth, record, parsed)
        else:
            gate = _DispatchGate(throttle, sleeper)

            def dispatch(item: tuple[str, int]) -> tuple[str, int, PageRecord, dict | None]:
                url, depth = item
                gate.wait_turn()
                record, parsed = fetch_one(
                    url,
                    client=client,
                    fetcher=fetcher,
                    throttle=throttle,
                    extra_headers=_extra_headers_for(url),
                )
                return url, depth, record, parsed

            with ThreadPoolExecutor(max_workers=max_concurrency) as pool:
                while queue and not stopped:
                    if len(result.pages) >= limit:
                        result.partial = True
                        result.stopped_reason = f"url limit reached ({limit})"
                        result.finish_reason = "url_limit"
                        break
                    if max_seconds and (clock() - crawl_started) >= max_seconds:
                        result.partial = True
                        result.stopped_reason = f"duration limit reached ({max_seconds:.0f}s)"
                        result.finish_reason = "duration_limit"
                        break

                    # One batch is one slice of the frontier, sized to what the
                    # origin has earned so far — never more than the pool has
                    # workers for, since that is the largest unit that stays
                    # sound to re-sort by discovery order in one pass.
                    batch = [queue.popleft() for _ in range(min(throttle.concurrency, len(queue)))]

                    blocked_depths = []
                    to_fetch = []
                    for u, d in batch:
                        if robots_blocks(u):
                            blocked_depths.append(d)
                        else:
                            to_fetch.append((u, d))

                    # A URL budget ends the crawl at an exact page count,
                    # concurrency or not: anything past the remaining budget
                    # goes back to the front of the queue rather than being
                    # dispatched.
                    budget = limit - len(result.pages)
                    if len(to_fetch) > budget:
                        overflow, to_fetch = to_fetch[budget:], to_fetch[:budget]
                        for item in reversed(overflow):
                            queue.appendleft(item)

                    # Depth bookkeeping matches the sequential walk: it covers
                    # every item popped for good (fetched or robots-blocked),
                    # never an item pushed back to the queue as overflow.
                    for d in blocked_depths:
                        result.max_depth_reached = max(result.max_depth_reached, d)
                    for _, d in to_fetch:
                        result.max_depth_reached = max(result.max_depth_reached, d)

                    if not to_fetch:
                        continue

                    # ``pool.map`` yields results in the order of ``to_fetch``
                    # regardless of which request actually finished first, so
                    # every downstream step — recording, the circuit breaker,
                    # link and redirect enqueueing — sees the same order the
                    # sequential crawler would have used.
                    processed = 0
                    interrupted = False
                    try:
                        for url, depth, record, parsed in pool.map(dispatch, to_fetch):
                            processed += 1
                            if after_fetch(url, depth, record, parsed):
                                stopped = True
                                break
                    except KeyboardInterrupt:
                        # Some workers in this batch may still be running; the
                        # ones whose result was never consumed here are not
                        # known to be processed, so they (and anything not yet
                        # dispatched) go back to the front of the queue rather
                        # than being dropped from the frontier.
                        interrupted = True

                    if interrupted or stopped:
                        for item in reversed(to_fetch[processed:]):
                            queue.appendleft(item)
                    if interrupted:
                        result.partial = True
                        result.stopped_reason = "interrupted"
                        result.finish_reason = "interrupted"
                        stopped = True

        if state_path:
            if result.finish_reason == "finished":
                # Nothing left to resume: a later call with the same path
                # should crawl fresh, not "resume" into an empty frontier.
                crawl_state.clear(state_path)
            else:
                # Saved only once the loop above has finished folding the last
                # batch back in, so the frontier on disk is always a complete
                # BFS state, never a snapshot taken mid-batch.
                crawl_state.save(
                    state_path,
                    crawl_state.CrawlState(
                        start_url=start,
                        queue=list(queue),
                        seen=sorted(seen),
                        max_depth_reached=result.max_depth_reached,
                        config_fingerprint=config_fingerprint,
                    ),
                )

    result.excluded = excluded
    result.effective_delay = throttle.delay
    result.effective_concurrency = throttle.concurrency
    result.limitations = [
        f"scope {rules.internal}: links outside it are recorded, never fetched",
        "static HTML only: no JavaScript rendering",
    ]
    if not seed_urls:
        # The spider itself never fetches a sitemap; a caller expands one and
        # passes the URL set in via seed_urls. When it did, this crawl was
        # sitemap-seeded, so the blanket limitation would be false.
        result.limitations.append("no sitemap expansion")
    return result
