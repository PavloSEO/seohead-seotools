"""Rule engine for checks derived from ``Internal:All``.

Each function reads the normalized pages and emits issues via ``ctx.add``.
Checks apply only where they make sense (HTML/indexable) and degrade quietly
when a column the data would need is absent.
"""

from __future__ import annotations

import re
import urllib.parse
from collections import defaultdict
from typing import Any

from seohead.tools.parser import robots_directives

from .context import AuditContext
from .models import Page
from .normalize import norm_url

NON_ASCII = re.compile(r"[^\x00-\x7F]")

# Tracking/ad/click-ID parameters that create session-specific URLs and pollute
# the index when they leak into indexable pages. Whole-param-name match.
TRACKING_PARAM_RE = re.compile(
    r"^(?:"
    r"utm_[a-z_]+"  # utm_source/medium/campaign/term/content/id/...
    r"|gcl(?:id|src)"  # Google Ads click & source
    r"|fbclid"  # Facebook
    r"|msclkid"  # Microsoft
    r"|yclid"  # Yandex Direct
    r"|dclid"  # DoubleClick
    r"|w?braid"  # gbraid/wbraid (Google Ads new-format)
    r"|_hs(?:enc|mi)"  # HubSpot
    r"|mc_[ce]id"  # Mailchimp campaign/eid
    r"|pk_(?:campaign|kwd|source|medium|content)"  # Piwik/Matomo
    r"|vero_(?:id|conv)"  # Vero
    r"|trksid?"  # eBay/LinkedIn tracking
    r"|cmpid"  # generic campaign id
    r"|mbid"  # marketo/bid
    r")$",
    re.IGNORECASE,
)


def _tracking_params(url: str) -> list[str]:
    """Param names on ``url`` that look like tracking IDs (empty == clean)."""
    qs = urllib.parse.urlsplit(url).query
    if not qs:
        return []
    return [k for k in urllib.parse.parse_qs(qs) if TRACKING_PARAM_RE.match(k)]


def _rec(page: Page) -> dict[str, Any]:
    return page.metrics.get("_record", {})


def _path_of(url: str) -> str:
    # the path only — query/fragment must not leak into path-based checks
    return urllib.parse.urlsplit(url).path


def _decoded_path(url: str) -> str:
    """The path as a reader sees it, with percent-escapes resolved.

    Exports carry the URL as crawled, so a path written in a non-Latin script
    arrives percent-encoded, one three-character escape per byte. RFC 3986
    prefers uppercase hex digits in those escapes, which makes the encoded form
    of every such URL look uppercase and none of them look non-ASCII — the
    exact opposite of the truth. Both questions are about the characters the
    path denotes, so both are asked of the decoded form.
    """
    return urllib.parse.unquote(_path_of(url))


# --------------------------------------------------------------------------
# 7.A — response codes & indexing
# --------------------------------------------------------------------------
def check_response_codes(ctx: AuditContext) -> None:
    for page in ctx.pages:
        code = page.status_code
        if code is None:
            continue
        if code == 0:
            ctx.add(
                "NO_RESPONSE", target_url=page.url, status_code=0, details={"status": page.status}
            )
        elif 400 <= code <= 499:
            ctx.add(
                "BROKEN_PAGE_4XX",
                target_url=page.url,
                status_code=code,
                details={"status": page.status, "inlinks": _rec(page).get("inlinks")},
            )
        elif 500 <= code <= 599:
            ctx.add(
                "SERVER_ERROR_5XX",
                target_url=page.url,
                status_code=code,
                details={"status": page.status},
            )


def check_indexability(ctx: AuditContext) -> None:
    for page in ctx.pages:
        status = (page.indexability_status or "").lower()
        if "blocked by robots" in status:
            inlinks = _rec(page).get("inlinks")
            ctx.add(
                "BLOCKED_BY_ROBOTS",
                target_url=page.url,
                details={"indexability_status": page.indexability_status, "inlinks": inlinks},
            )
            # blocked AND internally linked => robots blocks crawl of a live, linked page
            if inlinks and inlinks > 0:
                ctx.add(
                    "IMPORTANT_URL_BLOCKED_BY_ROBOTS",
                    target_url=page.url,
                    details={"inlinks": inlinks, "indexability_status": page.indexability_status},
                )
        if page.is_html and not page.is_indexable:
            inlinks = _rec(page).get("inlinks")
            if inlinks is not None and inlinks > 0 and page.status_code == 200:
                ctx.add(
                    "NON_INDEXABLE_LINKED",
                    target_url=page.url,
                    details={"indexability_status": page.indexability_status, "inlinks": inlinks},
                )


# Permanence is carried by the status code, not by the Redirect Type column:
# that column names the mechanism ("HTTP Redirect", "HSTS Policy",
# "JavaScript Redirect", "MetaRefresh Redirect") and never the word temporary.
TEMPORARY_REDIRECTS = (302, 303, 307)


def check_redirect_type(ctx: AuditContext) -> None:
    for page in ctx.pages:
        if page.status_code not in TEMPORARY_REDIRECTS:
            continue
        rec = _rec(page)
        ctx.add(
            "BAD_REDIRECT_TYPE",
            target_url=page.url,
            status_code=page.status_code,
            details={
                "redirect_type": rec.get("redirect_type"),
                "redirect_url": rec.get("redirect_url"),
            },
        )


# --------------------------------------------------------------------------
# 7.C — title & meta description
# --------------------------------------------------------------------------
def check_titles(ctx: AuditContext) -> None:
    t = ctx.thresholds
    for page in ctx.indexable_html_pages():
        rec = _rec(page)
        title = rec.get("title")
        if not title:
            ctx.add("TITLE_MISSING", target_url=page.url)
            continue
        length = rec.get("title_length")
        if length is None:  # 0 is a valid length; only fall back when truly absent
            length = len(str(title))
        px = rec.get("title_px")
        if length > t["title_max_chars"] or (px and px > t["title_max_px"]):
            ctx.add(
                "TITLE_TOO_LONG",
                target_url=page.url,
                details={
                    "title": title,
                    "length": length,
                    "pixel_width": px,
                    "max_chars": t["title_max_chars"],
                },
            )
        elif length < t["title_min_chars"]:
            ctx.add(
                "TITLE_TOO_SHORT",
                target_url=page.url,
                details={"title": title, "length": length, "min_chars": t["title_min_chars"]},
            )
        h1 = rec.get("h1")
        if h1 and str(h1).strip() == str(title).strip():
            ctx.add("TITLE_EQUALS_H1", target_url=page.url, details={"value": title})


def check_descriptions(ctx: AuditContext) -> None:
    t = ctx.thresholds
    for page in ctx.indexable_html_pages():
        rec = _rec(page)
        desc = rec.get("meta_description")
        if not desc:
            ctx.add("DESC_MISSING", target_url=page.url)
            continue
        length = rec.get("desc_length")
        if length is None:
            length = len(str(desc))
        px = rec.get("desc_px")
        if length > t["desc_max_chars"] or (px and px > t["desc_max_px"]):
            ctx.add(
                "DESC_TOO_LONG",
                target_url=page.url,
                details={"length": length, "max_chars": t["desc_max_chars"]},
            )
        elif length < t["desc_min_chars"]:
            ctx.add(
                "DESC_TOO_SHORT",
                target_url=page.url,
                details={"length": length, "min_chars": t["desc_min_chars"]},
            )


# --------------------------------------------------------------------------
# 7.D — headings (incl. multiple H1)
# --------------------------------------------------------------------------
def check_headings(ctx: AuditContext) -> None:
    t = ctx.thresholds
    require_h2 = ctx.requirements.get("require_h2", False)
    for page in ctx.indexable_html_pages():
        rec = _rec(page)
        h1 = rec.get("h1")
        h1_2 = rec.get("h1_2")
        if not h1:
            ctx.add("H1_MISSING", target_url=page.url)
        if h1_2:
            # Preserve each H1 value so reports identify which headings caused
            # the multiple-H1 finding instead of merely returning a count.
            ctx.add(
                "H1_MULTIPLE",
                target_url=page.url,
                details={
                    "h1_count": page.metrics["h1_count"],
                    "h1_texts": [v for v in (h1, h1_2) if v],
                },
            )
        h1_len = rec.get("h1_length")
        if h1 and h1_len and h1_len > t["h1_max_chars"]:
            ctx.add(
                "H1_TOO_LONG",
                target_url=page.url,
                details={"length": h1_len, "max_chars": t["h1_max_chars"]},
            )
        if require_h2 and h1 and not rec.get("h2"):
            ctx.add("H2_MISSING", target_url=page.url, details={"h1": h1})


# --------------------------------------------------------------------------
# 7.E — canonical & directives
# --------------------------------------------------------------------------
def check_canonical_directives(ctx: AuditContext) -> None:
    require_canonical = ctx.requirements.get("require_canonical", True)
    for page in ctx.html_pages():
        rec = _rec(page)
        canonical = rec.get("canonical")
        if page.is_indexable:
            if require_canonical and not canonical:
                ctx.add("CANONICAL_MISSING", target_url=page.url)
            elif canonical and norm_url(canonical) != norm_url(page.url):
                ctx.add("CANONICALISED", target_url=page.url, details={"canonical": canonical})
                # match the canonical target tolerant of trailing slash / case
                target = ctx.page_by_norm.get(norm_url(canonical))
                if target is not None and not target.is_indexable:
                    ctx.add(
                        "CANONICAL_NON_INDEXABLE",
                        target_url=page.url,
                        details={"canonical": canonical},
                    )
        robots = robots_directives(rec.get("meta_robots"), rec.get("x_robots"))
        if "noindex" in robots:
            ctx.add("NOINDEX", target_url=page.url, details={"meta_robots": rec.get("meta_robots")})
        elif "nofollow" in robots and page.is_indexable:
            ctx.add(
                "NOFOLLOW_PAGE",
                target_url=page.url,
                details={"meta_robots": rec.get("meta_robots")},
            )
        if rec.get("meta_keywords"):
            ctx.add(
                "META_KEYWORDS_PRESENT",
                target_url=page.url,
                details={"value": rec.get("meta_keywords")},
            )


# --------------------------------------------------------------------------
# 7.F — content: thin & near-duplicates (exact dupes handled in groups)
# --------------------------------------------------------------------------
def check_content(ctx: AuditContext) -> None:
    t = ctx.thresholds
    for page in ctx.indexable_html_pages():
        rec = _rec(page)
        wc = rec.get("word_count")
        if wc is not None and wc < t["thin_content_words"]:
            ctx.add(
                "THIN_CONTENT",
                target_url=page.url,
                details={"word_count": wc, "threshold": t["thin_content_words"]},
            )
        ratio = rec.get("text_ratio")
        if ratio is not None and ratio < t["low_text_ratio_pct"]:
            ctx.add(
                "LOW_TEXT_RATIO",
                target_url=page.url,
                details={"text_ratio": ratio, "threshold": t["low_text_ratio_pct"]},
            )
        near = rec.get("near_duplicates")
        sim = rec.get("closest_similarity")
        if near is not None and near > 0:
            ctx.add(
                "NEAR_DUPLICATE",
                target_url=page.url,
                details={"near_duplicates": near, "closest_similarity": sim},
            )


# --------------------------------------------------------------------------
# 7.I/7.J — URL hygiene, depth, performance, security
# --------------------------------------------------------------------------
def check_url_and_perf(ctx: AuditContext) -> None:
    t = ctx.thresholds
    for page in ctx.html_pages():
        rec = _rec(page)
        url = page.url
        path = _decoded_path(url)
        if len(url) > t["url_max_chars"]:
            ctx.add(
                "URL_TOO_LONG",
                target_url=url,
                details={"length": len(url), "max_chars": t["url_max_chars"]},
            )
        if "?" in url and page.is_indexable and not rec.get("canonical"):
            ctx.add("URL_HAS_PARAMS", target_url=url)
        if NON_ASCII.search(path):
            ctx.add("URL_NON_ASCII", target_url=url)
        if path != path.lower():  # True iff the path has an uppercase letter
            ctx.add("URL_UPPERCASE", target_url=url)
        if url.startswith("http://"):
            ctx.add("HTTP_URL", target_url=url)
        depth = rec.get("crawl_depth")
        if depth is not None and depth > t["crawl_depth_max"]:
            ctx.add(
                "DEEP_CRAWL_DEPTH",
                target_url=url,
                details={"crawl_depth": depth, "max": t["crawl_depth_max"]},
            )
        inlinks = rec.get("inlinks")
        # depth != 0 excludes the homepage; missing depth (None) still counts
        if (
            inlinks is not None
            and inlinks < t["orphan_inlinks_min"]
            and page.is_indexable
            and depth != 0
        ):
            ctx.add("ORPHAN_PAGE", target_url=url, details={"inlinks": inlinks})
        rt = rec.get("response_time")
        if rt is not None and rt > t["response_time_max_s"]:
            ctx.add(
                "SLOW_RESPONSE",
                target_url=url,
                details={"response_time": rt, "max_s": t["response_time_max_s"]},
            )


def check_schema(ctx: AuditContext) -> None:
    found_any = False
    for page in ctx.html_pages():
        ve = _rec(page).get("validation_errors")
        if ve is not None:
            found_any = True
        if ve and ve > 0:
            ctx.add(
                "SCHEMA_VALIDATION_ERROR", target_url=page.url, details={"validation_errors": ve}
            )
    if not found_any:
        ctx.skip("SCHEMA_VALIDATION_ERROR", "no Structured Data validation columns in Internal:All")


# --------------------------------------------------------------------------
# Duplicate grouping (TITLE / DESC / HASH) — emits groups + per-URL issues
# --------------------------------------------------------------------------
def check_duplicates(ctx: AuditContext) -> None:
    by_title: dict[str, list[str]] = defaultdict(list)
    by_desc: dict[str, list[str]] = defaultdict(list)
    by_hash: dict[str, list[str]] = defaultdict(list)
    by_h1: dict[str, list[str]] = defaultdict(list)
    has_hash = False
    for page in ctx.indexable_html_pages():
        rec = _rec(page)
        if rec.get("title"):
            by_title[str(rec["title"]).strip()].append(page.url)
        if rec.get("meta_description"):
            by_desc[str(rec["meta_description"]).strip()].append(page.url)
        if rec.get("hash"):
            has_hash = True
            by_hash[str(rec["hash"]).strip()].append(page.url)
        if rec.get("h1"):
            by_h1[str(rec["h1"]).strip()].append(page.url)

    def emit(groups: dict[str, list[str]], check_id: str) -> None:
        for value, urls in groups.items():
            if len(urls) < 2:
                continue
            group = ctx.add_group(check_id, value, sorted(urls))
            for url in urls:
                ctx.add(
                    check_id,
                    target_url=url,
                    group_id=group.group_id,
                    details={
                        "value": value if check_id != "DUPLICATE_BY_HASH" else None,
                        "duplicate_count": len(urls),
                    },
                )

    emit(by_title, "TITLE_DUPLICATE")
    emit(by_desc, "DESC_DUPLICATE")
    emit(by_h1, "H1_DUPLICATE")
    if has_hash:
        emit(by_hash, "DUPLICATE_BY_HASH")
    else:
        ctx.skip("DUPLICATE_BY_HASH", "no Hash/Page Hash column in Internal:All")


# --------------------------------------------------------------------------
# Extension checks — squeeze more out of the Internal:All columns
# --------------------------------------------------------------------------
def check_url_extra(ctx: AuditContext) -> None:
    for page in ctx.html_pages():
        url = page.url
        path = _path_of(url)
        if "_" in path:
            ctx.add("URL_UNDERSCORES", target_url=url)
        if "//" in path:
            ctx.add("URL_MULTIPLE_SLASHES", target_url=url)
        if " " in url or "%20" in url:
            ctx.add("URL_CONTAINS_SPACE", target_url=url)
        # A repeated *word* means a duplicated prefix or a crawl trap
        # (/shop/shop/, /en/products/en/). A repeated *number* means a
        # coordinate: /2024/01/01/ is the default WordPress permalink and
        # /catalog/12/12/ a pair of ids, so numeric segments are not compared.
        segs = [s for s in path.split("/") if s and not s.isdigit()]
        if len(segs) >= 2 and len(segs) != len(set(segs)):
            ctx.add("URL_REPETITIVE_PATH", target_url=url, details={"path": path})
        # Tracking params matter only on indexable URLs (else they're not going
        # to be crawled/indexed anyway).
        if page.is_indexable:
            tp = _tracking_params(url)
            if tp:
                ctx.add("URL_TRACKING_PARAMS", target_url=url, details={"params": tp})


def check_content_quality(ctx: AuditContext) -> None:
    t = ctx.thresholds
    has_read = has_awps = has_spell = has_grammar = False
    for page in ctx.indexable_html_pages():
        rec = _rec(page)
        flesch = rec.get("flesch")
        readability = rec.get("readability")
        if flesch is not None or readability is not None:
            has_read = True
            # difficult by Flesch score OR by SF's text label ("Difficult"/"Very Difficult")
            difficult = (flesch is not None and flesch < t["readability_flesch_min"]) or (
                readability is not None and "difficult" in str(readability).lower()
            )
            if difficult:
                ctx.add(
                    "READABILITY_DIFFICULT",
                    target_url=page.url,
                    details={
                        "flesch": flesch,
                        "readability": readability,
                        "min": t["readability_flesch_min"],
                    },
                )
        awps = rec.get("avg_words_per_sentence")
        if awps is not None:
            has_awps = True
            if awps > t["avg_words_per_sentence_max"]:
                ctx.add(
                    "LONG_SENTENCES",
                    target_url=page.url,
                    details={
                        "avg_words_per_sentence": awps,
                        "max": t["avg_words_per_sentence_max"],
                    },
                )
        sp = rec.get("spelling_errors")
        if sp is not None:
            has_spell = True
            if sp > 0:
                ctx.add("SPELLING_ERRORS", target_url=page.url, details={"count": sp})
        gr = rec.get("grammar_errors")
        if gr is not None:
            has_grammar = True
            if gr > 0:
                ctx.add("GRAMMAR_ERRORS", target_url=page.url, details={"count": gr})
    if not has_read:
        ctx.skip("READABILITY_DIFFICULT", "no Readability/Flesch column")
    if not has_awps:
        ctx.skip("LONG_SENTENCES", "no Average Words Per Sentence column")
    if not has_spell:
        ctx.skip("SPELLING_ERRORS", "no Spelling Errors column (enable spell-check in SF)")
    if not has_grammar:
        ctx.skip("GRAMMAR_ERRORS", "no Grammar Errors column (enable grammar-check in SF)")


def check_directives_extra(ctx: AuditContext) -> None:
    for page in ctx.html_pages():
        rec = _rec(page)
        robots = robots_directives(rec.get("meta_robots"), rec.get("x_robots"))
        if "noarchive" in robots:
            ctx.add("NOARCHIVE", target_url=page.url)
        if "nosnippet" in robots:
            ctx.add("NOSNIPPET", target_url=page.url)
        if "noimageindex" in robots:
            ctx.add("NOIMAGEINDEX", target_url=page.url)
        if rec.get("meta_refresh"):
            ctx.add(
                "META_REFRESH_REDIRECT",
                target_url=page.url,
                details={"meta_refresh": rec.get("meta_refresh")},
            )


def check_canonical_extra(ctx: AuditContext) -> None:
    for page in ctx.html_pages():
        rec = _rec(page)
        canonical = rec.get("canonical")
        if canonical and not canonical.lower().startswith(("http://", "https://", "//")):
            ctx.add("CANONICAL_RELATIVE", target_url=page.url, details={"canonical": canonical})
        if rec.get("canonical_2"):
            ctx.add(
                "CANONICAL_MULTIPLE",
                target_url=page.url,
                details={"canonical_1": canonical, "canonical_2": rec.get("canonical_2")},
            )


# --------------------------------------------------------------------------
# Canonical-graph checks build the canonical edge graph over
# Internal:All and flag multi-hop chains and canonicals onto redirects.
# --------------------------------------------------------------------------
def _canonical_edges(ctx: AuditContext) -> tuple[dict[str, str], bool]:
    """Return (norm_url -> norm_url edge map, has_any_canonical).

    An edge A→B exists when A's canonical differs from itself. Self-canonicals
    and absent canonicals produce no edge. ``has_any_canonical`` is True iff any
    page carried a canonical value (drives the honest skip).
    """
    edges: dict[str, str] = {}
    has_any = False
    for page in ctx.html_pages():
        canonical = _rec(page).get("canonical")
        if not canonical:
            continue
        has_any = True
        a = norm_url(page.url)
        b = norm_url(canonical)
        if a != b:
            edges[a] = b
    return edges, has_any


def check_canonical_chain(ctx: AuditContext) -> None:
    """CANONICAL_CHAIN — A→B where B itself canonicalizes onward (or back).

    A page is flagged when its canonical target has an outgoing canonical edge
    of its own (1-step lookahead over the edge graph). This covers both chains
    (A→B→C) and loops (A→B→A): in either case the target re-canonicalizes, so a
    search engine may resolve the canonical unpredictably. The full path is
    reconstructed for the report.
    """
    edges, has_any = _canonical_edges(ctx)
    if not has_any:
        ctx.skip("CANONICAL_CHAIN", "no Canonical column in Internal:All")
        return
    for page in ctx.html_pages():
        start = norm_url(page.url)
        b = edges.get(start)
        if b is None or b not in edges:
            continue  # no edge, or healthy single-step canonical to a terminal
        # target re-canonicalizes — reconstruct the path for context
        path = [start]
        seen = {start}
        cur = start
        is_loop = False
        for _ in range(8):  # bounded walk — guards against pathological graphs
            nxt = edges.get(cur)
            if nxt is None:
                break
            if nxt in seen:
                is_loop = True
                break
            path.append(nxt)
            seen.add(nxt)
            cur = nxt
        chain = []
        for n in path:
            tgt = ctx.page_by_norm.get(n)
            chain.append(tgt.url if tgt else n)
        ctx.add(
            "CANONICAL_CHAIN",
            target_url=page.url,
            details={"chain": chain, "depth": len(path) - 1, "loop": is_loop},
        )


def check_canonical_to_redirect(ctx: AuditContext) -> None:
    """CANONICAL_TO_REDIRECT — canonical target is itself a 3xx redirect.

    Cross-references the canonical URL against the crawl: a canonical target
    that responds 3xx (or carries a Redirect URL) forces an extra hop and lets
    the search engine choose its own canonical. Only targets present in the
    crawl can be classified; unknown URLs are left alone.
    """
    _, has_any = _canonical_edges(ctx)
    if not has_any:
        ctx.skip("CANONICAL_TO_REDIRECT", "no Canonical column in Internal:All")
        return
    for page in ctx.html_pages():
        canonical = _rec(page).get("canonical")
        if not canonical or norm_url(canonical) == norm_url(page.url):
            continue
        target = ctx.page_by_norm.get(norm_url(canonical))
        if target is None:
            continue  # external / not crawled — cannot classify
        code = target.status_code
        redirect_url = ctx.redirect_map.get(target.url)
        is_redirect = (code is not None and 300 <= code <= 399) or bool(redirect_url)
        if is_redirect:
            ctx.add(
                "CANONICAL_TO_REDIRECT",
                target_url=page.url,
                details={
                    "canonical": canonical,
                    "canonical_status_code": code,
                    "redirect_url": redirect_url or target.url,
                },
            )


def check_pagination(ctx: AuditContext) -> None:
    for page in ctx.html_pages():
        rec = _rec(page)
        if (rec.get("rel_next") or rec.get("rel_prev")) and not page.is_indexable:
            ctx.add(
                "PAGINATION_NONINDEXABLE",
                target_url=page.url,
                details={"indexability_status": page.indexability_status},
            )


def check_links_extra(ctx: AuditContext) -> None:
    t = ctx.thresholds
    for page in ctx.indexable_html_pages():
        rec = _rec(page)
        outlinks = rec.get("outlinks")
        external = rec.get("external_outlinks")
        if outlinks is not None:
            internal = outlinks - (external or 0)
            if internal <= 0:
                ctx.add(
                    "NO_INTERNAL_OUTLINKS",
                    target_url=page.url,
                    details={"outlinks": outlinks, "external_outlinks": external},
                )
            if outlinks > t["high_outlinks"]:
                ctx.add(
                    "HIGH_OUTLINKS",
                    target_url=page.url,
                    details={"outlinks": outlinks, "max": t["high_outlinks"]},
                )
        if external is not None and external > t["high_external_outlinks"]:
            ctx.add(
                "HIGH_EXTERNAL_OUTLINKS",
                target_url=page.url,
                details={"external_outlinks": external, "max": t["high_external_outlinks"]},
            )


def check_tech_extra(ctx: AuditContext) -> None:
    for page in ctx.html_pages():
        rec = _rec(page)
        # SF emits HTTP Version as "HTTP/1.1", "HTTP/2" or bare "1.1"/"2"; str() because
        # an all-numeric column parses as float.
        hv = str(rec.get("http_version") or "").upper().replace("HTTP/", "").strip()
        if hv.startswith("1"):
            ctx.add(
                "HTTP1_ONLY", target_url=page.url, details={"http_version": rec.get("http_version")}
            )
        if rec.get("amphtml"):
            ctx.add("AMPHTML_PRESENT", target_url=page.url, details={"amphtml": rec.get("amphtml")})


def check_og(ctx: AuditContext) -> None:
    """Check Open Graph presence.

    Fires on indexable HTML pages missing ``og:title`` — the one tag without
    which a social preview cannot assemble. Honesty contract: if the export
    carries no OG columns at all (user didn't enable OG extraction in SF), the
    check skips rather than flag every page.
    """
    pages = ctx.indexable_html_pages()
    og_fields = ("og_title", "og_description", "og_image", "og_url")
    has_og = any(_rec(p).get(k) for p in pages for k in og_fields)
    if not has_og:
        ctx.skip("OG_MISSING", "no Open Graph columns in Internal:All (enable OG extraction in SF)")
        return
    for page in pages:
        rec = _rec(page)
        if rec.get("og_title"):
            continue
        missing = [
            f.replace("_", ":") for f in ("og_title", "og_image", "og_url") if not rec.get(f)
        ]
        ctx.add("OG_MISSING", target_url=page.url, details={"missing_tags": missing})


# Native-filter exports: emit one issue per Address when the export is present,
# else honestly skip (no dead zeros). export key -> check id.
_NATIVE_EXPORT_CHECKS = {
    "security_mixed": "MIXED_CONTENT",
    "security_hsts": "MISSING_HSTS",
    "structured_data_missing": "STRUCTURED_DATA_MISSING",
    "images_over_kb": "IMG_OVER_KB",
    "images_missing_size": "IMG_MISSING_DIMENSIONS",
    "images_missing_alt": "IMG_MISSING_ALT",
    "titles_multiple": "TITLE_MULTIPLE",
    "hreflang": "HREFLANG_ERROR",
}


def check_redirect_chains(ctx: AuditContext) -> None:
    """Consume the Redirects:Redirect Chains report (full profile)."""
    from .normalize import find_column, normalize_value, to_int

    df = ctx.exports.get("redirect_chains")
    if df is None or df.empty:
        ctx.skip("REDIRECT_CHAIN", "no Redirect Chains report (export Redirects:Redirect Chains)")
        ctx.skip("REDIRECT_LOOP", "no Redirect Chains report (export Redirects:Redirect Chains)")
        return
    addr = find_column(df, ["Address", "URL"])
    hops = find_column(
        df, ["Number of Redirects", "No. Of Redirects", "No. of Redirects", "Redirect Hops", "Hops"]
    )
    final = find_column(df, ["Final Address", "Final URL", "Final URI"])
    loop = find_column(df, ["Loop", "Redirect Loop", "Chain Loop"])
    if not addr:
        ctx.skip("REDIRECT_CHAIN", "Redirect Chains report has no address column")
        return
    for _, row in df.iterrows():
        url = normalize_value(row.get(addr))
        if not url:
            continue
        n = to_int(row.get(hops)) if hops else None
        fin = normalize_value(row.get(final)) if final else None
        is_loop = loop and str(normalize_value(row.get(loop))).strip().lower() in (
            "true",
            "yes",
            "1",
        )
        if is_loop:
            ctx.add("REDIRECT_LOOP", target_url=url, details={"hops": n, "final_url": fin})
        elif n is not None and n >= 2:
            ctx.add("REDIRECT_CHAIN", target_url=url, details={"hops": n, "final_url": fin})


def check_native_exports(ctx: AuditContext) -> None:
    from .normalize import find_column, normalize_value

    for key, check_id in _NATIVE_EXPORT_CHECKS.items():
        df = ctx.exports.get(key)
        if df is None or df.empty:
            ctx.skip(check_id, f"no {key} export (export this SF filter to enable)")
            continue
        col = find_column(df, ["Address", "URL", "Image URL", "Image"])
        if not col:
            ctx.skip(check_id, f"{key} export has no address column")
            continue
        for value in df[col].tolist():
            url = normalize_value(value)
            if url:
                ctx.add(check_id, target_url=url, evidence={"export": ctx.exports.files.get(key)})


ALL_CHECKS = [
    check_response_codes,
    check_indexability,
    check_redirect_type,
    check_titles,
    check_descriptions,
    check_headings,
    check_canonical_directives,
    check_content,
    check_url_and_perf,
    check_schema,
    check_duplicates,
    # extensions — maximize extraction from Internal:All
    check_url_extra,
    check_content_quality,
    check_directives_extra,
    check_canonical_extra,
    check_canonical_chain,
    check_canonical_to_redirect,
    check_pagination,
    check_links_extra,
    check_tech_extra,
    check_og,
    check_redirect_chains,
    check_native_exports,
]


def run_rules(ctx: AuditContext) -> None:
    """Run every Internal:All-derived check against the context."""
    if ctx.internal_df is None:
        ctx.skip("INTERNAL_ALL", "Internal:All export not loaded")
        return
    for check in ALL_CHECKS:
        check(ctx)
