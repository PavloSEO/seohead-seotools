"""Bounded fetching of an explicit URL list.

List mode is a strict subset of a crawler: no frontier, no scope model, no
traps, so its output is deterministic by construction. It is also the slice that
does real work on day one — verifying a redirect map after a migration,
re-checking the URLs a developer says are fixed, auditing a Search Console
export.

Rows are written as they are collected. Screaming Frog writes its exports only
at the end, which is why a measured 75-minute polite crawl of a struggling host
produced nothing at all; a collector that batches to the end inherits that
failure exactly where crawling is hardest.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from typing import Any

from seohead.crawl.throttle import Throttle
from seohead.recon.net import UA, http_client, pinned_target, validate_url
from seohead.tools.parser import parse_html

SCHEMA_VERSION = "crawl.v1"

MAX_URLS_CEILING = 10_000
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
DEFAULT_TIMEOUT_S = 15.0


@dataclass
class PageRecord:
    """One fetched URL, in the collector's own vocabulary."""

    url: str
    status_code: int | None = None
    content_type: str = ""
    size_bytes: int = 0
    response_time: float | None = None
    redirect_url: str = ""
    title: str = ""
    meta_description: str = ""
    h1: str = ""
    h1_2: str = ""
    h2: str = ""
    canonical: str = ""
    meta_robots: str = ""
    x_robots: str = ""
    og_title: str = ""
    og_description: str = ""
    og_image: str = ""
    word_count: int = 0
    text_ratio: float | None = None
    crawl_depth: int = 0
    outlinks: int = 0
    external_outlinks: int = 0
    jsonld_blocks_found: int = 0
    jsonld_blocks_parsed: int = 0
    error: str = ""

    @property
    def is_html(self) -> bool:
        return "html" in (self.content_type or "").lower()


@dataclass
class CrawlResult:
    schema_version: str = SCHEMA_VERSION
    pages: list[PageRecord] = field(default_factory=list)
    partial: bool = False
    stopped_reason: str = ""
    limitations: list[str] = field(default_factory=list)


def _text_of(value: Any) -> str:
    return "" if value is None else str(value)


def _first_heading(parsed: dict, level: str, index: int = 0) -> str:
    items = (parsed.get("headings") or {}).get(level) or []
    return _text_of(items[index]) if len(items) > index else ""


def _record_from_parsed(parsed: dict) -> dict[str, Any]:
    og = parsed.get("og") or {}
    links = parsed.get("links") or []
    return {
        "title": _text_of(parsed.get("title")),
        "meta_description": _text_of(parsed.get("meta_description")),
        "h1": _first_heading(parsed, "h1", 0),
        "h1_2": _first_heading(parsed, "h1", 1),
        "h2": _first_heading(parsed, "h2", 0),
        "canonical": _text_of(parsed.get("canonical")),
        "meta_robots": _text_of(parsed.get("robots")),
        "og_title": _text_of(og.get("title")),
        "og_description": _text_of(og.get("description")),
        "og_image": _text_of(og.get("image")),
        "word_count": int(parsed.get("word_count") or 0),
        "outlinks": len(links),
        "external_outlinks": len([link for link in links if link.get("external")]),
    }


# Match the script tag, not the media type wherever it appears. Counting the
# substring double-counts on any framework that echoes its own markup into a
# hydration payload: one real block on a Next.js page was counted twice, which
# across a crawl reported "found 408, parsed 200" for a site whose JSON-LD is
# fine. A false alarm of that shape is worse than no check.
_JSONLD_TAG_RE = re.compile(r"<script[^>]+application/ld\+json", re.IGNORECASE)


def _jsonld_counts(html: str, parsed: dict) -> tuple[int, int]:
    """Blocks present in the markup, and blocks that actually parsed.

    A page carrying one malformed block must be reported as "found 1, parsed 0".
    Reporting "no structured data" would describe a different page.
    """
    return len(_JSONLD_TAG_RE.findall(html)), len(parsed.get("jsonld") or [])


def fetch_one(
    url: str,
    *,
    client: Any = None,
    fetcher: Callable[[str], Any] | None = None,
    throttle: Throttle | None = None,
) -> tuple[PageRecord, dict[str, Any] | None]:
    """Fetch and parse one URL. Returns the record and the parsed document.

    The parsed document is handed back rather than discarded so a caller that
    needs the links — the spider — does not parse the same bytes twice.
    """
    record = PageRecord(url=url)
    if fetcher is None:
        # Guard only the transport we open ourselves. validate_url resolves DNS,
        # so running it against an injected transport would make offline tests
        # depend on the network and would guard a socket we never open.
        try:
            validate_url(url)
        except Exception as exc:  # blocked target, bad scheme, private network
            record.error = str(exc)
            return record, None

    started = time.monotonic()
    try:
        if fetcher:
            response = fetcher(url)
        else:
            # Connect to the address that was vetted, keeping the hostname for
            # SNI and certificate verification. Resolving twice would leave a
            # window between the check and the connection.
            target, headers, extensions = pinned_target(url)
            response = client.get(
                target,
                headers={"User-Agent": UA, **headers},
                extensions=extensions,
            )
    except Exception as exc:
        record.error = str(exc)
        if throttle is not None and _is_timeout(str(exc)):
            throttle.record_timeout()
        return record, None

    elapsed = time.monotonic() - started
    record.response_time = round(elapsed, 3)
    record.status_code = getattr(response, "status_code", None)
    headers = {k.lower(): v for k, v in dict(getattr(response, "headers", {})).items()}
    record.content_type = headers.get("content-type", "")
    record.x_robots = headers.get("x-robots-tag", "")
    record.redirect_url = headers.get("location", "")

    body = getattr(response, "text", "") or ""
    record.size_bytes = len(body.encode("utf-8", "ignore"))
    ok = record.status_code is not None and 200 <= record.status_code < 300
    if throttle is not None:
        throttle.record_response(elapsed, ok)
        code = record.status_code or 0
        if code == 429 or 500 <= code < 600:
            throttle.record_server_error(code, _retry_after(headers.get("retry-after")))
        else:
            throttle.record_success()

    parsed = None
    if record.size_bytes > MAX_RESPONSE_BYTES:
        # Too large to parse, but a 200 is still a 200: not "unreachable".
        record.error = "response too large to parse"
    elif record.is_html and body:
        parsed = parse_html(body, url)
        for key, value in _record_from_parsed(parsed).items():
            setattr(record, key, value)
        found, parsed_count = _jsonld_counts(body, parsed)
        record.jsonld_blocks_found = found
        record.jsonld_blocks_parsed = parsed_count
        text_len = len(_text_of(parsed.get("text")).encode("utf-8", "ignore"))
        record.text_ratio = round(text_len / record.size_bytes, 4) if record.size_bytes else None
    return record, parsed


def _retry_after(value: str | None) -> float | None:
    """Seconds from a Retry-After header. Only the numeric form is honoured."""
    if not value:
        return None
    try:
        return max(0.0, float(value.strip()))
    except ValueError:
        return None  # HTTP-date form: respected as "back off", not as a duration


def _is_timeout(message: str) -> bool:
    lowered = message.lower()
    return "timed out" in lowered or "timeout" in lowered


def collect_urls(
    urls: Iterable[str],
    *,
    max_urls: int = 500,
    timeout: float = DEFAULT_TIMEOUT_S,
    min_delay: float = 0.0,
    out_path: str | None = None,
    fetcher: Callable[[str], Any] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> CrawlResult:
    """Fetch an explicit list of URLs in the order given.

    ``out_path`` receives one JSON object per line as each URL completes, so an
    interrupted run still leaves usable evidence behind.
    """
    limit = max(1, min(int(max_urls), MAX_URLS_CEILING))
    result = CrawlResult()
    throttle = Throttle(min_delay=min_delay)

    seen: set[str] = set()
    with contextlib.ExitStack() as stack:
        handle = None
        if out_path:
            os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
            handle = stack.enter_context(open(out_path, "w", encoding="utf-8"))

        client = None
        if fetcher is None:
            client, _ = http_client(timeout)
            stack.callback(client.close)

        for raw in urls:
            if len(result.pages) >= limit:
                result.partial = True
                result.stopped_reason = f"url limit reached ({limit})"
                break
            url = (raw or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)

            if throttle.delay:
                sleeper(throttle.delay)

            record, _ = fetch_one(url, client=client, fetcher=fetcher, throttle=throttle)
            result.pages.append(record)
            _write(handle, record)

            if throttle.should_stop():
                result.partial = True
                result.stopped_reason = "origin stopped responding (repeated timeouts)"
                break
            if throttle.host_is_failing():
                result.partial = True
                result.stopped_reason = "origin refused repeatedly (429/5xx) — crawl stopped"
                break

    result.limitations = [
        "list mode: no link discovery, no sitemap expansion",
        "static HTML only: no JavaScript rendering",
    ]
    return result


def _write(handle, record: PageRecord) -> None:
    if handle is None:
        return
    handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    handle.flush()
