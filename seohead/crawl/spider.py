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
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from seohead.crawl.collect import CrawlResult, _write, fetch_one
from seohead.crawl.throttle import Throttle
from seohead.recon.net import http_client, normalize_url
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


def _canonical_key(url: str) -> str:
    """Identity for de-duplication: fragment dropped, nothing else rewritten."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))


def _same_host(url: str, host: str) -> bool:
    return (urlsplit(url).hostname or "").lower() == host


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
    min_delay: float = 0.5,
    timeout: float = 15.0,
    robots_policy: str = "respect",
    out_path: str | None = None,
    fetcher: Callable[[str], Any] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> SpiderResult:
    """Crawl one host breadth-first from ``start_url``."""
    start = normalize_url(start_url)
    host = (urlsplit(start).hostname or "").lower() if start else ""
    # normalize_url is lenient — it turns "not a url" into "https://not a url" —
    # so the host is checked here rather than trusted.
    if not start or not host or " " in host or "." not in host:
        raise ValueError(f"not a crawlable URL: {start_url!r}")
    limit = max(1, min(int(max_urls), MAX_URLS_CEILING))
    depth_limit = max(0, min(int(max_depth), MAX_DEPTH_CEILING))

    result = SpiderResult()
    throttle = Throttle(min_delay=min_delay)
    excluded: dict[str, int] = {}

    def exclude(reason: str) -> None:
        excluded[reason] = excluded.get(reason, 0) + 1

    with contextlib.ExitStack() as stack:
        handle = None
        if out_path:
            handle = stack.enter_context(open(out_path, "w", encoding="utf-8"))
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
            return result

        # A site asking to be crawled slowly is asking the crawler, not the
        # operator. The configured delay is a floor, never a ceiling on politeness.
        asked = crawl_delay(robots, ROBOTS_TOKEN) if robots else None
        if asked and asked > throttle.min_delay:
            throttle.min_delay = asked
            throttle.delay = max(throttle.delay, asked)
            result.crawl_delay_applied = asked

        queue: deque[tuple[str, int]] = deque([(start, 0)])
        seen: set[str] = {_canonical_key(start)}

        while queue:
            if len(result.pages) >= limit:
                result.partial = True
                result.stopped_reason = f"url limit reached ({limit})"
                break
            url, depth = queue.popleft()
            result.max_depth_reached = max(result.max_depth_reached, depth)

            if robots and not is_allowed(robots, match_path(url), ROBOTS_TOKEN):
                result.robots_blocked.append(url)
                if enforce:
                    exclude("blocked_by_robots")
                    continue

            if throttle.delay:
                sleeper(throttle.delay)

            record, parsed = fetch_one(url, client=client, fetcher=fetcher, throttle=throttle)
            record.crawl_depth = depth
            result.pages.append(record)
            _write(handle, record)

            if throttle.should_stop():
                result.partial = True
                result.stopped_reason = "origin stopped responding (repeated timeouts)"
                break
            if throttle.host_is_failing():
                # The host has refused repeatedly. Continuing would measure the
                # crawler rather than the site.
                result.partial = True
                result.stopped_reason = "origin refused repeatedly (429/5xx) — crawl stopped"
                break

            # A redirect is a discovery too, and it stays inside the budget.
            if record.redirect_url and depth < depth_limit:
                target = record.redirect_url
                if _same_host(target, host):
                    key = _canonical_key(target)
                    if key not in seen:
                        seen.add(key)
                        queue.append((target, depth + 1))
                else:
                    exclude("redirect_off_host")

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
                if not _same_host(href, host):
                    exclude("outside_host")
                    continue
                key = _canonical_key(href)
                if key in seen:
                    continue
                seen.add(key)
                queue.append((href, depth + 1))

    result.excluded = excluded
    result.effective_delay = throttle.delay
    result.limitations = [
        "same-host only: external links are recorded, never fetched",
        "static HTML only: no JavaScript rendering",
        "no sitemap expansion",
    ]
    return result
