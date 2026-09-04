"""Link localization from ``*:Inlinks`` bulk exports.

This is the module that answers the core request: a broken link — *where it
sits* (source page), *where it goes* (destination), *where in the DOM*
(Link Position + Link Path/XPath), and *on how many pages*. One issue per
destination URL, with every source as a location.
"""

from __future__ import annotations

import re
import urllib.parse
from collections import Counter, OrderedDict
from typing import Any

from seohead.tools.hreflang import code_error

from .context import AuditContext
from .models import Link
from .normalize import HREFLANG_FIELD_MAP, INLINKS_FIELD_MAP, is_true, norm_url, records_from_df

# logical export key -> (internal-destination check, external-destination check).
# The *:Inlinks exports include links to BOTH internal and external destinations;
# we split by host so an external 404 isn't mislabeled as an internal one.
INLINK_SOURCES = {
    "inlinks_4xx": ("BROKEN_INTERNAL_LINK", "BROKEN_EXTERNAL_LINK"),
    "inlinks_5xx": ("LINK_TO_5XX", "BROKEN_EXTERNAL_LINK"),
    "inlinks_3xx": ("INTERNAL_LINK_TO_REDIRECT", "EXTERNAL_LINK_TO_REDIRECT"),
}


def _site_host(ctx: AuditContext) -> str:
    counts: Counter = Counter()
    for page in ctx.pages:
        host = urllib.parse.urlparse(page.url).netloc.lower()
        if host:
            counts[host] += 1
    return counts.most_common(1)[0][0] if counts else ""


def _link_from_record(rec: dict[str, Any]) -> Link:
    follow_raw = rec.get("follow")
    return Link(
        source_url=rec.get("source_url"),
        destination_url=rec.get("destination_url"),
        anchor=rec.get("anchor"),
        alt_text=rec.get("alt_text"),
        status_code=rec.get("status_code"),
        link_position=rec.get("link_position"),
        link_path=rec.get("link_path"),
        follow=is_true(follow_raw) if follow_raw is not None else None,
        rel=rec.get("rel"),
        target=rec.get("target"),
    )


def _process_export(
    ctx: AuditContext, key: str, internal_check: str, external_check: str, site_host: str
) -> None:
    df = ctx.exports.get(key)
    if df is None or df.empty:
        ctx.skip(internal_check, f"export {key} not available")
        ctx.skip(external_check, f"export {key} not available")
        return

    max_locs = ctx.config.get("output", {}).get("max_locations_per_issue", 200)
    by_dest: OrderedDict[str, list[Link]] = OrderedDict()
    for rec in records_from_df(df, INLINKS_FIELD_MAP):
        link = _link_from_record(rec)
        if not link.destination_url:
            continue
        by_dest.setdefault(link.destination_url, []).append(link)

    for dest, links in by_dest.items():
        dest_host = urllib.parse.urlparse(dest).netloc.lower()
        is_internal = (not dest_host) or (dest_host == site_host)
        check_id = internal_check if is_internal else external_check
        status = next((link.status_code for link in links if link.status_code), None)
        details: dict[str, Any] = {
            "link_position_breakdown": _position_breakdown(links),
            "destination_scope": "internal" if is_internal else "external",
        }
        if check_id == "INTERNAL_LINK_TO_REDIRECT":
            final = ctx.redirect_map.get(dest)
            if final:
                details["final_url"] = final
        locations = [link.as_location() for link in links[:max_locs]]
        # Count distinct source pages, not raw link occurrences. This answers
        # "on how many pages does this link appear?" when a page repeats it.
        n_sources = len({link.source_url for link in links if link.source_url})
        ctx.add(
            check_id,
            target_url=dest,
            status_code=status,
            occurrences_count=n_sources or len(links),
            locations=locations,
            details=details,
            evidence={"export": ctx.exports.files.get(key)},
        )


def _position_breakdown(links: list[Link]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for link in links:
        pos = link.link_position or "Unknown"
        counts[pos] = counts.get(pos, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Generic anchor text
# ---------------------------------------------------------------------------
# Curated Russian-and-English dictionary of non-descriptive anchors. Match the
# entire normalized anchor after lowercasing, collapsing whitespace, and
# trimming surrounding punctuation. This catches "Read More", localized
# equivalents, and variants such as "  click here…", but not a meaningful
# phrase such as "click here to buy" where the remaining words add context.
_GENERIC_ANCHORS = frozenset(
    {
        # Russian
        "тут",
        "здесь",
        "далее",
        "подробнее",
        "сюда",
        "ссылка",
        "читать далее",
        "читать дальше",
        "читайте далее",
        "читайте дальше",
        "по ссылке",
        "перейти по ссылке",
        "перейдите по ссылке",
        "нажмите здесь",
        "узнать больше",
        "больше",
        "смотрите тут",
        # English
        "here",
        "click here",
        "read more",
        "learn more",
        "more",
        "see more",
        "view more",
        "click",
        "link",
        "this",
        "this link",
        "continue reading",
        "check it out",
        "details",
    }
)

_GENERIC_ANCHOR_TRIM = " \t\u00a0.,;:!?«»\"'()[]{}…—–-"  # noqa: RUF001 - punctuation set


def _norm_anchor(anchor: str) -> str:
    cleaned = re.sub(r"\s+", " ", anchor.lower()).strip()
    return cleaned.strip(_GENERIC_ANCHOR_TRIM).strip()


def check_anchor_text(ctx: AuditContext) -> None:
    """Flag localized non-descriptive anchors such as "here" and "click here".

    Scans every available ``*:Inlinks`` export (``all_inlinks`` preferred; the
    status-code reports as fallback). The fix lives on the *source* page, so one
    issue is emitted per source URL, with each generic link in ``details``. If no
    inlinks export is loaded the check skips honestly rather than emit zeros.
    """
    max_locs = ctx.config.get("output", {}).get("max_locations_per_issue", 200)
    export_keys = [
        k
        for k in ("all_inlinks", "inlinks_4xx", "inlinks_5xx", "inlinks_3xx")
        if ctx.exports.has(k) and not ctx.exports.get(k).empty
    ]
    if not export_keys:
        ctx.skip(
            "GENERIC_ANCHOR_TEXT",
            "no *:Inlinks export available (export 'All Inlinks' or any *:Inlinks report)",
        )
        return

    seen: set[tuple[str | None, str | None, str]] = set()
    by_source: OrderedDict[str, list[Link]] = OrderedDict()
    for key in export_keys:
        for rec in records_from_df(ctx.exports.get(key), INLINKS_FIELD_MAP):
            link = _link_from_record(rec)
            anchor = link.anchor
            if not anchor or not link.source_url:
                continue
            if _norm_anchor(anchor) not in _GENERIC_ANCHORS:
                continue
            dedup = (link.source_url, link.destination_url, anchor.strip().lower())
            if dedup in seen:
                continue
            seen.add(dedup)
            by_source.setdefault(link.source_url, []).append(link)

    for source, links in by_source.items():
        generic_links = [
            {
                "anchor": link.anchor,
                "destination": link.destination_url,
                "link_position": link.link_position,
            }
            for link in links[:max_locs]
        ]
        ctx.add(
            "GENERIC_ANCHOR_TEXT",
            target_url=source,
            occurrences_count=len(links),
            locations=[link.as_location() for link in links[:max_locs]],
            details={"generic_links": generic_links},
            evidence={
                "exports": export_keys,
                "files": [ctx.exports.files.get(k) for k in export_keys],
            },
        )


# ---------------------------------------------------------------------------
# hreflang -> broken target
# ---------------------------------------------------------------------------
def check_hreflang_targets(ctx: AuditContext) -> None:
    """HREFLANG_BROKEN_TARGET — hreflang points at a 3xx/4xx/5xx URL.

    Reads the Bulk Export → Links → ``All Hreflang`` report (one row per
    hreflang annotation: source → target URL + lang). Each target is matched
    against the crawl: a target that responds 3xx/4xx/5xx (or carries a Redirect
    URL) breaks international localization and is flagged on its source page.
    Targets not in the crawl (external cross-domain hreflang) cannot be
    classified and are skipped silently. If the export is absent the check
    skips honestly rather than emit a dead zero.
    """
    df = ctx.exports.get("all_hreflang")
    if df is None or df.empty:
        ctx.skip(
            "HREFLANG_BROKEN_TARGET",
            "no all_hreflang export (export Bulk Export → Links → All Hreflang to enable)",
        )
        return

    by_source: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    seen_pairs: set[tuple[str, str]] = set()
    for rec in records_from_df(df, HREFLANG_FIELD_MAP):
        src = rec.get("source_url")
        dest = rec.get("destination_url")
        if not src or not dest:
            continue
        target = ctx.page_by_norm.get(norm_url(dest))
        if target is None:
            continue  # external / not crawled — cannot classify the target
        code = target.status_code
        redirect_url = ctx.redirect_map.get(target.url)
        is_redirect = (code is not None and 300 <= code <= 399) or bool(redirect_url)
        is_error = code is not None and code >= 400
        if not (is_redirect or is_error):
            continue
        pair = (src, dest)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        by_source.setdefault(src, []).append(
            {
                "hreflang": rec.get("hreflang"),
                "target_url": dest,
                "status_code": code,
                "redirect_url": redirect_url,
            }
        )

    for source, targets in by_source.items():
        ctx.add(
            "HREFLANG_BROKEN_TARGET",
            target_url=source,
            occurrences_count=len(targets),
            details={"broken_targets": targets},
            evidence={"export": ctx.exports.files.get("all_hreflang")},
        )


def _rec(page: Any) -> dict[str, Any]:
    return page.metrics.get("_record", {})


# ---------------------------------------------------------------------------
# hreflang -> code/self-reference/x-default/duplicate/canonical quality
# ---------------------------------------------------------------------------
_HREFLANG_QUALITY_CHECKS = (
    "HREFLANG_INVALID_CODE",
    "HREFLANG_MULTIPLE_ENTRIES",
    "HREFLANG_MISSING_SELF_REFERENCE",
    "HREFLANG_MISSING_XDEFAULT",
    "HREFLANG_NOT_CANONICAL",
)


def check_hreflang_quality(ctx: AuditContext) -> None:
    """Validate each page's own hreflang set: codes, duplicates, self, x-default, canonical.

    Reads the same Bulk Export → Links → ``All Hreflang`` report as
    :func:`check_hreflang_targets` (one row per source → destination + lang
    annotation) and reuses the ISO 639-1/3166-1 validator already shipped for
    the single-URL ``seo_hreflang_check`` tool (:func:`seohead.tools.hreflang.
    code_error`) instead of re-implementing it. Every check here groups by the
    declaring page (source), matching how a browser or crawler reads one
    page's hreflang set. If the export is absent, all five checks skip
    honestly rather than emit dead zeros.
    """
    df = ctx.exports.get("all_hreflang")
    if df is None or df.empty:
        for check_id in _HREFLANG_QUALITY_CHECKS:
            ctx.skip(
                check_id, "no all_hreflang export (export Bulk Export -> Links -> All Hreflang)"
            )
        return

    by_source: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for rec in records_from_df(df, HREFLANG_FIELD_MAP):
        src = rec.get("source_url")
        if not src or not rec.get("destination_url"):
            continue
        by_source.setdefault(src, []).append(rec)

    evidence = {"export": ctx.exports.files.get("all_hreflang")}
    for source, entries in by_source.items():
        _check_invalid_codes(ctx, source, entries, evidence)
        _check_duplicate_entries(ctx, source, entries, evidence)
        _check_self_reference(ctx, source, entries, evidence)
        _check_xdefault(ctx, source, entries, evidence)
        _check_not_canonical(ctx, source, entries, evidence)


def _check_invalid_codes(
    ctx: AuditContext, source: str, entries: list[dict[str, Any]], evidence: dict[str, Any]
) -> None:
    invalid = []
    for rec in entries:
        lang = rec.get("hreflang")
        if not lang:
            continue
        reason = code_error(lang)
        if reason:
            invalid.append(
                {"hreflang": lang, "destination": rec.get("destination_url"), "reason": reason}
            )
    if invalid:
        ctx.add(
            "HREFLANG_INVALID_CODE",
            target_url=source,
            occurrences_count=len(invalid),
            details={"invalid": invalid},
            evidence=evidence,
        )


def _check_duplicate_entries(
    ctx: AuditContext, source: str, entries: list[dict[str, Any]], evidence: dict[str, Any]
) -> None:
    # Language tags are case-insensitive: "en-US" declared twice (even with
    # different casing) is the same annotation twice, not two annotations.
    folded = [str(rec["hreflang"]).strip().lower() for rec in entries if rec.get("hreflang")]
    duplicates = sorted({lang for lang in folded if folded.count(lang) > 1})
    if duplicates:
        ctx.add(
            "HREFLANG_MULTIPLE_ENTRIES",
            target_url=source,
            occurrences_count=len(duplicates),
            details={"duplicate_values": duplicates},
            evidence=evidence,
        )


def _check_self_reference(
    ctx: AuditContext, source: str, entries: list[dict[str, Any]], evidence: dict[str, Any]
) -> None:
    source_norm = norm_url(source)
    destinations = {norm_url(rec.get("destination_url")) for rec in entries}
    if source_norm not in destinations:
        ctx.add(
            "HREFLANG_MISSING_SELF_REFERENCE",
            target_url=source,
            details={"declared_targets": sorted({rec["destination_url"] for rec in entries})},
            evidence=evidence,
        )


def _check_xdefault(
    ctx: AuditContext, source: str, entries: list[dict[str, Any]], evidence: dict[str, Any]
) -> None:
    folded = {str(rec["hreflang"]).strip().lower() for rec in entries if rec.get("hreflang")}
    if "x-default" not in folded:
        ctx.add("HREFLANG_MISSING_XDEFAULT", target_url=source, evidence=evidence)


def _check_not_canonical(
    ctx: AuditContext, source: str, entries: list[dict[str, Any]], evidence: dict[str, Any]
) -> None:
    offenders = []
    for rec in entries:
        dest = rec.get("destination_url")
        target = ctx.page_by_norm.get(norm_url(dest))
        if target is None:
            continue  # external / not crawled — cannot classify
        canonical = _rec(target).get("canonical")
        if canonical and norm_url(canonical) != norm_url(target.url):
            offenders.append(
                {"hreflang": rec.get("hreflang"), "destination": dest, "canonical": canonical}
            )
    if offenders:
        ctx.add(
            "HREFLANG_NOT_CANONICAL",
            target_url=source,
            occurrences_count=len(offenders),
            details={"non_canonical_targets": offenders},
            evidence=evidence,
        )


def run_inlinks(ctx: AuditContext) -> None:
    site_host = _site_host(ctx)
    for key, (internal_check, external_check) in INLINK_SOURCES.items():
        _process_export(ctx, key, internal_check, external_check, site_host)
    check_anchor_text(ctx)
    check_hreflang_targets(ctx)
    check_hreflang_quality(ctx)
