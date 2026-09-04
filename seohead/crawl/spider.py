"""Breadth-first link discovery — the part that makes this a crawler.

Fetching a list someone else produced tests the fetcher. Following links is the
thing that closes the gap: without it the toolkit cannot obtain a URL list of
its own, which is the whole reason this module exists.

Traversal is deterministic given identical responses: the frontier is a queue,
children are enqueued in document order rather than sorted, and every exclusion
is recorded as data rather than dropped silently.
"""

from __future__ import annotations

import contextlib
import dataclasses
import json
import os
import re
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from seohead.crawl import state as crawl_state
from seohead.crawl.collect import CrawlResult, PageRecord, _write, fetch_one
from seohead.crawl.config import resolve_credential_headers
from seohead.crawl.throttle import Throttle
from seohead.recon.net import http_client, normalize_url, registrable_domain
from seohead.tools.robots import crawl_delay, is_allowed, match_path, parse_robots

MAX_URLS_CEILING = 10_000
MAX_DEPTH_CEILING = 20
ROBOTS_TOKEN = "SEOHEAD-Tools"
EMPTY_ROBOTS = {"allow": [], "disallow": [], "groups": [], "crawl_delay": None}


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
    # Why the checkpoint was or wasn't used, for the run output — see state.py.
    resume_note: str = ""


def _canonical_key(url: str) -> str:
    """Identity for de-duplication: fragment dropped, nothing else rewritten."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))


def _same_host(url: str, host: str) -> bool:
    return (urlsplit(url).hostname or "").lower() == host


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
    out_path: str | None = None,
    state_path: str | None = None,
    config_fingerprint: str = "",
    fetcher: Callable[[str], Any] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    credential_headers: list[dict[str, Any]] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> SpiderResult:
    """Crawl one host breadth-first from ``start_url``, within ``scope``.

    ``max_seconds`` is a wall-clock budget for the whole call; 0 means none.
    ``state_path``, when given, checkpoints the frontier there so a later call
    with the same path and start URL resumes instead of restarting —
    ``config_fingerprint`` is compared too, so a scope or limit change since the
    checkpoint starts fresh rather than mixing frontiers built under different
    rules.
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
    if state_path:
        crawl_state.ensure_safe_dir(os.path.dirname(os.path.abspath(state_path)) or ".")

    result = SpiderResult()
    throttle = Throttle(min_delay=min_delay)
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

        while queue:
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

            if robots and not is_allowed(robots, match_path(url), ROBOTS_TOKEN):
                result.robots_blocked.append(url)
                if enforce:
                    exclude("blocked_by_robots")
                    continue

            # Resolved for this hop's own host, never carried over from the
            # last one — that is what keeps a credential off a cross-host
            # redirect target.
            extra_headers = (
                resolve_credential_headers(credential_headers, urlsplit(url).hostname or "")
                if credential_headers
                else None
            )
            try:
                if throttle.delay:
                    sleeper(throttle.delay)
                record, parsed = fetch_one(
                    url,
                    client=client,
                    fetcher=fetcher,
                    throttle=throttle,
                    extra_headers=extra_headers,
                )
            except KeyboardInterrupt:
                # Not processed: put it back so a resume retries it rather than
                # silently dropping it from the frontier.
                queue.appendleft((url, depth))
                result.partial = True
                result.stopped_reason = "interrupted"
                result.finish_reason = "interrupted"
                break
            record.crawl_depth = depth
            result.pages.append(record)
            _write(handle, record)

            if throttle.should_stop():
                result.partial = True
                result.stopped_reason = "origin stopped responding (repeated timeouts)"
                result.finish_reason = "errors"
                break
            if throttle.host_is_failing():
                # The host has refused repeatedly. Continuing would measure the
                # crawler rather than the site.
                result.partial = True
                result.stopped_reason = "origin refused repeatedly (429/5xx) — crawl stopped"
                result.finish_reason = "errors"
                break

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

            if parsed is None:
                continue
            if depth >= depth_limit:
                exclude("depth_limit")
                continue

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

        if state_path:
            if result.finish_reason == "finished":
                # Nothing left to resume: a later call with the same path
                # should crawl fresh, not "resume" into an empty frontier.
                crawl_state.clear(state_path)
            else:
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
    result.limitations = [
        f"scope {rules.internal}: links outside it are recorded, never fetched",
        "static HTML only: no JavaScript rendering",
        "no sitemap expansion",
    ]
    return result
