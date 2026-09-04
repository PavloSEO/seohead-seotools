"""Sitemap and robots.txt audit.

Two independent sources, merged: (1) Screaming Frog's native ``Sitemaps:*``
exports when present, and (2) a direct parse of robots.txt / sitemap.xml (with
sitemap-index recursion and gzip) over the network. The direct parse uses only
the stdlib; ``advertools`` is used opportunistically if installed but is never
required. Network access is opt-in (``--sitemap`` or ``live_recheck.enabled``).
"""

from __future__ import annotations

import gzip
import io
import re
import statistics
import time
import urllib.parse
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from defusedxml import ElementTree as ET

from seohead.recon.net import http_client, validate_url

from .context import AuditContext
from .normalize import find_column, normalize_value

SITEMAP_DIRECTIVE = re.compile(r"^\s*sitemap:\s*(\S+)", re.IGNORECASE | re.MULTILINE)
_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

# Hardening bounds for the opt-in network parser.
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024  # cap a single download
MAX_DECOMPRESSED_BYTES = 100 * 1024 * 1024  # cap gunzip output (gzip-bomb guard)
MAX_SITEMAP_DEPTH = 5  # sitemapindex recursion depth
MAX_SITEMAP_URLS = 200_000  # total <loc> across the chain


def _host(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc.lower()
    except (ValueError, AttributeError):
        return ""


# --------------------------------------------------------------------------
# network helpers (opt-in)
# --------------------------------------------------------------------------
def _safe_gunzip(data: bytes) -> bytes:
    out = bytearray()
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as gz:
        while True:
            chunk = gz.read(65536)
            if not chunk:
                break
            out += chunk
            if len(out) > MAX_DECOMPRESSED_BYTES:
                raise ValueError("decompressed sitemap exceeds size limit")
    return bytes(out)


def _fetch(url: str, user_agent: str, timeout: int, retries: int = 2) -> bytes | None:
    if not url.lower().startswith(("http://", "https://")):  # no file://, ftp://, etc.
        return None
    try:
        validate_url(url)
    except ValueError:
        return None
    # Retry transient failures so a flaky host doesn't silently drop sitemap subtrees.
    for attempt in range(retries + 1):
        try:
            client, _http2_capable = http_client(
                timeout, follow_redirects=True, headers={"User-Agent": user_agent}
            )
            data = bytearray()
            with client, client.stream("GET", url) as response:
                response.raise_for_status()
                for chunk in response.iter_raw():
                    data += chunk
                    if len(data) > MAX_DOWNLOAD_BYTES:
                        return None
            data = bytes(data)
            if len(data) > MAX_DOWNLOAD_BYTES:
                return None
            if url.endswith(".gz") or data[:2] == b"\x1f\x8b":
                data = _safe_gunzip(data)
            return data
        except Exception:
            if attempt < retries:
                time.sleep(0.6 * (attempt + 1))
    return None


def _parse_sitemap_bytes(
    data: bytes,
    user_agent: str,
    timeout: int,
    seen: set[str],
    allowed_hosts: set[str],
    depth: int = 0,
    failures: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Return [{loc, lastmod}], recursing through <sitemapindex> with guards.

    Child sitemaps that can't be fetched are appended to ``failures`` (so the
    caller can report a partial parse instead of silently undercounting).
    """
    # Reject DTDs/entities outright — sitemaps never use them (XXE / billion-laughs guard).
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        return []
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []
    tag = root.tag.split("}")[-1]
    out: list[dict[str, Any]] = []
    if tag == "sitemapindex":
        if depth >= MAX_SITEMAP_DEPTH:
            return []
        for sm in root.findall("sm:sitemap", _NS) or root.findall("sitemap"):
            loc = sm.findtext("sm:loc", namespaces=_NS) or sm.findtext("loc")
            if not loc:
                continue
            loc = loc.strip()
            # SSRF guard: only follow children on an allowed host.
            if loc in seen or (allowed_hosts and _host(loc) not in allowed_hosts):
                continue
            seen.add(loc)
            child = _fetch(loc, user_agent, timeout)
            if child:
                out.extend(
                    _parse_sitemap_bytes(
                        child, user_agent, timeout, seen, allowed_hosts, depth + 1, failures
                    )
                )
            elif failures is not None:
                failures.append(loc)
            if len(out) >= MAX_SITEMAP_URLS:
                break
    else:  # urlset
        for url_el in root.findall("sm:url", _NS) or root.findall("url"):
            loc = url_el.findtext("sm:loc", namespaces=_NS) or url_el.findtext("loc")
            lastmod = url_el.findtext("sm:lastmod", namespaces=_NS) or url_el.findtext("lastmod")
            if loc:
                out.append({"loc": loc.strip(), "lastmod": (lastmod or "").strip() or None})
                if len(out) >= MAX_SITEMAP_URLS:
                    break
    return out


def _base_url(ctx: AuditContext) -> str | None:
    counts: Counter = Counter()
    for page in ctx.pages:
        parts = page.url.split("/", 3)
        if len(parts) >= 3:
            counts[f"{parts[0]}//{parts[2]}"] += 1
    return counts.most_common(1)[0][0] if counts else None


# --------------------------------------------------------------------------
# lastmod parsing
# --------------------------------------------------------------------------
def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


# --------------------------------------------------------------------------
# export-driven checks
# --------------------------------------------------------------------------
def _urls_from_export(ctx: AuditContext, key: str) -> list[str]:
    df = ctx.exports.get(key)
    if df is None or df.empty:
        return []
    col = find_column(df, ["Address", "URL"])
    if not col:
        return []
    return [normalize_value(v) for v in df[col].tolist() if normalize_value(v)]


def _emit_from_export(ctx: AuditContext, key: str, check_id: str) -> int:
    urls = _urls_from_export(ctx, key)
    for url in urls:
        ctx.add(
            check_id,
            target_url=url,
            details={"in_sitemap": True},
            evidence={"export": ctx.exports.files.get(key)},
        )
    return len(urls)


# --------------------------------------------------------------------------
# main entry
# --------------------------------------------------------------------------
def run_sitemap(ctx: AuditContext, sitemap_url: str | None = None) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    cfg_live = ctx.config.get("live_recheck", {})
    ua = cfg_live.get(
        "user_agent", "Mozilla/5.0 (compatible; SEOHEAD-Tools/3.0; +https://seohead.tech/seotools)"
    )
    timeout = cfg_live.get("timeout_s", 10)

    # --- 1. SF native Sitemaps:* exports ---------------------------------
    sf_in = _urls_from_export(ctx, "sitemap_in")
    _emit_from_export(ctx, "sitemap_non_200", "SITEMAP_URL_4XX_5XX")
    _emit_from_export(ctx, "sitemap_redirects", "SITEMAP_URL_3XX")
    _emit_from_export(ctx, "sitemap_non_indexable", "SITEMAP_URL_NON_INDEXABLE")
    _emit_from_export(ctx, "sitemap_orphan", "SITEMAP_ORPHAN")
    not_in = _urls_from_export(ctx, "sitemap_not_in")
    for url in not_in:
        ctx.add("URL_NOT_IN_SITEMAP", target_url=url)

    # --- 2. direct robots.txt + sitemap parse (opt-in) -------------------
    sitemap_entries: list[dict[str, Any]] = []
    declared_in_robots: bool | None = None
    sitemaps_declared: list[str] = []
    want_network = bool(sitemap_url) or cfg_live.get("enabled", False)
    base = _base_url(ctx)

    if want_network and base:
        robots = _fetch(f"{base}/robots.txt", ua, timeout)
        if robots is not None:
            robots_text = robots.decode("utf-8", "replace")
            sitemaps_declared = SITEMAP_DIRECTIVE.findall(robots_text)
            declared_in_robots = bool(sitemaps_declared)
            if not declared_in_robots:
                ctx.add("SITEMAP_NOT_IN_ROBOTS", target_url=base)
            # robots blocking render-critical resources breaks Google's rendering
            disallows = re.findall(r"(?im)^\s*disallow:\s*(\S+)", robots_text)
            res_re = re.compile(
                r"\.(?:js|css)\b|/_next/|/static/|/assets/|/js/|/css/", re.IGNORECASE
            )
            blocked_res = [d for d in disallows if res_re.search(d)]
            if blocked_res:
                ctx.add(
                    "ROBOTS_BLOCKS_RESOURCES", target_url=base, details={"rules": blocked_res[:10]}
                )
        targets = [sitemap_url] if sitemap_url else (sitemaps_declared or [f"{base}/sitemap.xml"])
        # SSRF allow-list: the base host plus the hosts of explicitly-given sitemaps.
        allowed_hosts = {_host(base)} | {_host(t) for t in targets if t}
        allowed_hosts.discard("")
        seen = set(targets)
        fetch_failures: list[str] = []
        for sm_url in targets:
            data = _fetch(sm_url, ua, timeout)
            if data:
                sitemap_entries.extend(
                    _parse_sitemap_bytes(
                        data, ua, timeout, seen, allowed_hosts, failures=fetch_failures
                    )
                )
            else:
                fetch_failures.append(sm_url)
        if fetch_failures:
            summary["sitemap_fetch_failures"] = fetch_failures[:20]
            ctx.add(
                "SITEMAP_FETCH_INCOMPLETE",
                target_url=base,
                details={"failed_count": len(fetch_failures), "examples": fetch_failures[:10]},
            )

    # Prefer the richer source for the URL set / lastmod analysis.
    sitemap_locs = [e["loc"] for e in sitemap_entries] or sf_in
    sitemap_set = set(sitemap_locs)

    # --- 3. lastmod staleness -------------------------------------------
    lastmod_summary = _analyze_lastmod(ctx, sitemap_entries)
    if lastmod_summary:
        summary["lastmod"] = lastmod_summary

    # --- 4. desync (both directions) ------------------------------------
    indexable = {p.url for p in ctx.indexable_html_pages()}
    in_sitemap_not_crawl = sorted(sitemap_set - {p.url for p in ctx.pages})
    in_crawl_not_sitemap = sorted(indexable - sitemap_set) if sitemap_set else []

    # mark pages with sitemap membership
    for page in ctx.pages:
        if sitemap_set:
            page.metrics["is_in_sitemap"] = page.url in sitemap_set

    if sitemap_set:
        threshold = ctx.thresholds["sitemap_desync_pct_warn"]
        # direction 1: indexable pages crawled but missing from the sitemap
        crawl_only_pct = round(100 * len(in_crawl_not_sitemap) / max(len(indexable), 1), 1)
        # direction 2: sitemap URLs the crawl never reached (orphan / unlinked / EN half / depth)
        sitemap_only_pct = round(100 * len(in_sitemap_not_crawl) / max(len(sitemap_set), 1), 1)
        if crawl_only_pct >= threshold or sitemap_only_pct >= threshold:
            ctx.add(
                "SITEMAP_DESYNC",
                target_url=base,
                details={
                    "in_crawl_not_in_sitemap": len(in_crawl_not_sitemap),
                    "in_sitemap_not_in_crawl": len(in_sitemap_not_crawl),
                    "crawl_not_in_sitemap_pct": crawl_only_pct,
                    "sitemap_not_in_crawl_pct": sitemap_only_pct,
                    "examples_missing_from_sitemap": in_crawl_not_sitemap[:20],
                    "examples_in_sitemap_not_crawled": in_sitemap_not_crawl[:20],
                },
            )
    else:
        ctx.skip("SITEMAP_DESYNC", "no sitemap URL set (no export and network disabled)")

    summary.update(
        {
            "declared_in_robots": declared_in_robots,
            "sitemaps": sitemaps_declared or ([sitemap_url] if sitemap_url else []),
            "urls_in_sitemap": len(sitemap_set),
            "urls_in_crawl_indexable": len(indexable),
            "in_sitemap_not_in_crawl": len(in_sitemap_not_crawl),
            "in_crawl_not_in_sitemap": len(in_crawl_not_sitemap),
            "non_200_in_sitemap": len(_urls_from_export(ctx, "sitemap_non_200")),
            "non_indexable_in_sitemap": len(_urls_from_export(ctx, "sitemap_non_indexable")),
        }
    )
    if sitemap_set:
        # Same three key names the native crawler's own reconciliation uses
        # (seohead.crawl.reconcile.reconcile_sitemap), so a consumer of
        # audit.json's summary.sitemap does not need two schemas depending on
        # which crawl mode produced the report. Full lists, not the capped
        # 20-item examples above — this is the first-class output, not a
        # threshold-gated issue detail.
        summary["in_sitemap_and_linked"] = sorted(sitemap_set & {p.url for p in ctx.pages})
        summary["in_sitemap_not_linked"] = in_sitemap_not_crawl
        summary["linked_not_in_sitemap"] = in_crawl_not_sitemap
    return summary


def _analyze_lastmod(ctx: AuditContext, entries: list[dict[str, Any]]) -> dict[str, Any]:
    dates: list[datetime] = []
    invalid = 0
    future = 0
    now = datetime.now(timezone.utc)
    for e in entries:
        if not e.get("lastmod"):
            continue
        dt = _parse_date(e["lastmod"])
        if dt is None:
            invalid += 1
            continue
        if dt > now:
            future += 1
            continue  # future dates are generation errors — keep them out of stats
        dates.append(dt)
    if not dates:
        return {}
    dates.sort()
    stale_days = ctx.thresholds["sitemap_lastmod_stale_days"]
    cutoff_secs = stale_days * 86400
    cutoff_share = sum(1 for d in dates if (now - d).total_seconds() > cutoff_secs) / len(dates)
    all_same = len({d.date() for d in dates}) == 1
    median_dt = datetime.fromtimestamp(
        statistics.median([d.timestamp() for d in dates]), tz=timezone.utc
    )
    summary = {
        "oldest": dates[0].date().isoformat(),
        "median": median_dt.date().isoformat(),
        "newest": dates[-1].date().isoformat(),
        "share_older_than_threshold": round(cutoff_share, 2),
        "threshold_days": stale_days,
        "all_identical": all_same,
        "invalid_count": invalid,
        "future_count": future,
    }
    if cutoff_share >= 0.5 or all_same or future or invalid:
        ctx.add("SITEMAP_STALE_LASTMOD", target_url=_base_url(ctx), details=summary)
    return summary
