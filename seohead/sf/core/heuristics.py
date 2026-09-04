"""Heuristics beyond native Screaming Frog findings: HTML weight anomalies, DOM size,
bytes/word and templated titles. These catch problems SF measures but never
marks as errors — e.g. "300 KB page where the site median is 70 KB".

Derived metrics are written back onto ``page.metrics`` even when no threshold
trips, so downstream analysis/LLMs have the raw signal.
"""

from __future__ import annotations

import os
import statistics
import urllib.parse
from collections import Counter
from typing import Any

from .context import AuditContext
from .normalize import find_column

SEPARATORS = (" | ", " — ", " - ", " · ", " :: ", " // ")

# A Tukey fence measures distance in units of spread, so it needs spread to
# exist. A templated site has almost none: every page renders the same shell,
# the interquartile range collapses to zero, and p75 + 1.5 * 0 degenerates into
# "heavier than the median" — which reports a page 0.2% above it as an outlier,
# on most of the site at once. Below this fraction of the median the sizes are
# one value at the resolution that matters, and only the absolute and
# multiple-of-median rules have anything to say.
MIN_IQR_FRACTION_OF_MEDIAN = 0.10


def _quantile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    pos = (len(sorted_vals) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def size_stats(ctx: AuditContext) -> dict[str, Any]:
    sizes = [p.metrics.get("size_bytes") for p in ctx.indexable_html_pages()]
    sizes = sorted(s for s in sizes if isinstance(s, (int, float)) and s > 0)
    if not sizes:
        return {}
    return {
        "count": len(sizes),
        "median": statistics.median(sizes),
        "p75": _quantile(sizes, 0.75),
        "p90": _quantile(sizes, 0.90),
        "p95": _quantile(sizes, 0.95),
        "max": sizes[-1],
        "iqr": _quantile(sizes, 0.75) - _quantile(sizes, 0.25),
    }


def check_html_weight(ctx: AuditContext) -> dict[str, Any]:
    stats = size_stats(ctx)
    if not stats:
        ctx.skip("LARGE_HTML", "no Size (bytes) data for HTML pages")
        ctx.skip("HTML_BLOAT", "no Size (bytes) data for HTML pages")
        return stats

    t = ctx.thresholds
    median = stats["median"] or 1
    abs_bytes = t["large_html_abs_kb"] * 1024
    k = t["large_html_x_median"]
    has_spread = stats["iqr"] >= median * MIN_IQR_FRACTION_OF_MEDIAN
    tukey_upper = stats["p75"] + 1.5 * stats["iqr"] if has_spread else None

    # rank the heaviest pages for the report
    ranked = sorted(
        (p for p in ctx.indexable_html_pages() if p.metrics.get("size_bytes")),
        key=lambda p: p.metrics["size_bytes"],
        reverse=True,
    )
    rank_of = {p.url: i + 1 for i, p in enumerate(ranked)}

    # bytes/word distribution for the bloat heuristic
    bpw_vals = []
    for page in ctx.indexable_html_pages():
        size = page.metrics.get("size_bytes")
        wc = page.metrics.get("word_count")
        if size and wc and wc > 0:
            bpw = size / wc
            page.metrics["bytes_per_word"] = round(bpw, 1)
            bpw_vals.append(bpw)
    bpw_median = statistics.median(bpw_vals) if bpw_vals else None

    for page in ctx.indexable_html_pages():
        size = page.metrics.get("size_bytes")
        if not size:
            continue
        ratio = size / median
        page.metrics["size_vs_median_ratio"] = round(ratio, 2)
        is_outlier = size > median * k or (tukey_upper is not None and size > tukey_upper)
        if size > abs_bytes or is_outlier:
            ctx.add(
                "LARGE_HTML",
                target_url=page.url,
                details={
                    "size_bytes": int(size),
                    "site_median": int(median),
                    "ratio": round(ratio, 2),
                    "rank": rank_of.get(page.url),
                    "abs_threshold_kb": t["large_html_abs_kb"],
                    "outlier": bool(is_outlier),
                },
            )
        bpw = page.metrics.get("bytes_per_word")
        if (
            bpw
            and bpw_median
            and bpw > bpw_median * t["bytes_per_word_x_median"]
            and (page.metrics.get("word_count") or 0) > 0
        ):
            ctx.add(
                "HTML_BLOAT",
                target_url=page.url,
                details={
                    "bytes_per_word": round(bpw, 1),
                    "site_median_bpw": round(bpw_median, 1),
                    "word_count": page.metrics.get("word_count"),
                    "size_bytes": int(size),
                },
            )
    return stats


# --------------------------------------------------------------------------
# DOM depth / nodes — only when SF stored the (rendered) HTML
# --------------------------------------------------------------------------
def _dom_metrics(html: str) -> tuple[int, int]:
    """Return (max nesting depth, element count) — single O(n) DFS, no parent walks."""
    from lxml import html as lxml_html

    tree = lxml_html.fromstring(html)
    nodes = 0
    max_depth = 0
    stack: list[tuple[Any, int]] = [(tree, 0)]
    while stack:
        el, depth = stack.pop()
        if isinstance(el.tag, str):  # skip comments / processing instructions
            nodes += 1
            max_depth = max(max_depth, depth)
        for child in el:
            stack.append((child, depth + 1))
    return max_depth, nodes


def check_dom(ctx: AuditContext) -> None:
    html_dir = ctx.config.get("input", {}).get("html_store_dir")
    if not html_dir or not os.path.isdir(html_dir):
        ctx.skip("DOM_TOO_DEEP", "no stored HTML (input.html_store_dir not set)")
        ctx.skip("DOM_TOO_MANY_NODES", "no stored HTML (input.html_store_dir not set)")
        return
    t = ctx.thresholds
    index = _build_html_index(html_dir)
    matched = 0
    for page in ctx.indexable_html_pages():
        path = _match_html_file(index, page.url)
        if not path:
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                depth, nodes = _dom_metrics(fh.read())
        except Exception:
            continue
        matched += 1
        page.metrics["dom_depth"] = depth
        page.metrics["dom_nodes"] = nodes
        if depth > t["dom_depth_max"]:
            ctx.add(
                "DOM_TOO_DEEP",
                target_url=page.url,
                details={"dom_depth": depth, "max": t["dom_depth_max"]},
            )
        if nodes > t["dom_nodes_max"]:
            ctx.add(
                "DOM_TOO_MANY_NODES",
                target_url=page.url,
                details={"dom_nodes": nodes, "max": t["dom_nodes_max"]},
            )
    if matched == 0:
        reason = "stored HTML present but no files mapped to crawled URLs"
        ctx.skip("DOM_TOO_DEEP", reason)
        ctx.skip("DOM_TOO_MANY_NODES", reason)


def _build_html_index(html_dir: str) -> dict[str, str]:
    """Index stored HTML files under several keys so URLs can be matched.

    SF's Store HTML writes a ``<dir>/<host>/<path>`` tree. We key each file by
    its path relative to ``html_dir`` (host+path) *and* its basename, so the
    lookup in :func:`_match_html_file` can try host+path first, then basename.
    """
    index: dict[str, str] = {}
    for root, _dirs, files in os.walk(html_dir):
        for name in files:
            if not name.lower().endswith((".html", ".htm")):
                continue
            full = os.path.join(root, name)
            rel = os.path.relpath(full, html_dir).replace(os.sep, "/").lower()
            index.setdefault(rel, full)
            index.setdefault(rel.lstrip("/"), full)
            index.setdefault(name.lower(), full)  # basename fallback (last wins)
    return index


def _match_html_file(index: dict[str, str], url: str) -> str | None:
    """Try host+path, then path, then basename — return the first hit."""
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path
    base = (os.path.basename(path) or "index.html").lower()
    candidates = []
    if host and path:
        hp = f"{host}{path}".lower()
        candidates += [hp, hp.rstrip("/") + "/index.html"]
    if path:
        candidates.append(path.lstrip("/").lower())
    candidates.append(base)
    for key in candidates:
        hit = index.get(key)
        if hit:
            return hit
    return None


# --------------------------------------------------------------------------
# Near-duplicate content — only when SF stored the HTML and did not already
# compute this itself (issue #15, item 3)
# --------------------------------------------------------------------------
def check_content_duplication(ctx: AuditContext) -> None:
    """NEAR_DUPLICATE / DUPLICATE_BY_HASH computed from stored page text.

    Near-duplicate clustering is an all-pairs comparison — any pair may
    include a page not yet fetched — so it can only run once the crawl is
    complete, over a stored corpus (issue #15, item 3). Screaming Frog's own
    Near Duplicates/Hash columns already answer this when the crawl exported
    them (``check_content``/``check_duplicates`` in rules.py); this only fills
    whichever half is missing, reusing the same ``input.html_store_dir`` HTML
    store ``check_dom`` reads, scoped to the configured content area so a
    shared nav/footer does not make every page look alike, and delegating the
    actual clustering to :func:`seohead.tools.duplicate.find_duplicates`
    (SimHash + LSH), which excludes exact-duplicate pairs from the near-dup
    clusters on its own.
    """
    has_native_near = ctx.internal_df is not None and find_column(
        ctx.internal_df, ["No. Near Duplicates"]
    )
    has_native_hash = ctx.internal_df is not None and find_column(
        ctx.internal_df, ["Hash", "Page Hash"]
    )
    if has_native_near:
        ctx.skip("NEAR_DUPLICATE", "SF native Near Duplicates column already covers this")
    if has_native_hash:
        ctx.skip("DUPLICATE_BY_HASH", "SF native Hash column already covers this")
    if has_native_near and has_native_hash:
        return  # nothing left for the stored-text pass to add

    html_dir = ctx.config.get("input", {}).get("html_store_dir")
    if not html_dir or not os.path.isdir(html_dir):
        if not has_native_near:
            ctx.skip("NEAR_DUPLICATE", "no stored HTML (input.html_store_dir not set)")
        if not has_native_hash:
            ctx.skip("DUPLICATE_BY_HASH", "no stored HTML (input.html_store_dir not set)")
        return

    from bs4 import BeautifulSoup

    from seohead.tools.content_area import extract_area_text, resolve_content_area
    from seohead.tools.duplicate import find_duplicates

    index = _build_html_index(html_dir)
    content_cfg = ctx.config.get("content_area", {})
    items: list[dict[str, Any]] = []
    for page in ctx.indexable_html_pages():
        path = _match_html_file(index, page.url)
        if not path:
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                html = fh.read()
        except OSError:
            continue
        root, _strategy = resolve_content_area(BeautifulSoup(html, "html.parser"), content_cfg)
        items.append({"id": page.url, "text": extract_area_text(root)})

    if not items:
        reason = "stored HTML present but no files mapped to crawled URLs"
        if not has_native_near:
            ctx.skip("NEAR_DUPLICATE", reason)
        if not has_native_hash:
            ctx.skip("DUPLICATE_BY_HASH", reason)
        return

    threshold = ctx.thresholds.get("near_duplicate_similarity", 0.92)
    result = find_duplicates(items, threshold=threshold)

    if not has_native_near:
        for cluster in result["clusters"]:
            members = sorted(cluster["members"])
            group = ctx.add_group("NEAR_DUPLICATE", None, members)
            for url in members:
                ctx.add(
                    "NEAR_DUPLICATE",
                    target_url=url,
                    group_id=group.group_id,
                    details={
                        "cluster_min_similarity": cluster["min_similarity"],
                        "cluster_size": len(members),
                    },
                )
    if not has_native_hash:
        for exact in result["exact_duplicates"]:
            members = sorted(exact["members"])
            group = ctx.add_group("DUPLICATE_BY_HASH", None, members)
            for url in members:
                ctx.add(
                    "DUPLICATE_BY_HASH",
                    target_url=url,
                    group_id=group.group_id,
                    details={"duplicate_count": len(members)},
                )


# --------------------------------------------------------------------------
# Templated titles: the same prefix or suffix across most pages
# --------------------------------------------------------------------------
def check_templated_titles(ctx: AuditContext) -> None:
    titles = [p.metrics.get("title") for p in ctx.indexable_html_pages()]
    titles = [str(t).strip() for t in titles if t]
    if len(titles) < 5:
        ctx.skip("TITLE_TEMPLATED", "too few titles to assess templating")
        return
    suffixes: Counter = Counter()
    for title in titles:
        for sep in SEPARATORS:
            if sep in title:
                suffixes[title.rsplit(sep, 1)[-1].strip()] += 1
                break
    if not suffixes:
        return
    top_suffix, count = suffixes.most_common(1)[0]
    share = count / len(titles)
    if share >= ctx.thresholds["templated_title_share"]:
        ctx.add(
            "TITLE_TEMPLATED",
            target_url=None,
            details={
                "suffix": top_suffix,
                "share": round(share, 2),
                "pages": count,
                "total": len(titles),
            },
        )


def run_heuristics(ctx: AuditContext) -> dict[str, Any]:
    stats = check_html_weight(ctx)
    check_dom(ctx)
    check_content_duplication(ctx)
    check_templated_titles(ctx)
    return stats
