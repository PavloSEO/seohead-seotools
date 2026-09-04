"""Projection of collected evidence onto the analyzer's input contract.

This is a projection onto Screaming Frog's schema, not a neutral format: the
analyzer resolves records by literal SF column headers, so the frames built here
carry those headers. There is exactly one consumer and it has SF's vocabulary.

The important half is what is *declared absent*. A native list-mode run cannot
produce redirect chains, near-duplicate similarity, readability, pixel widths or
link score, and a check that silently reports nothing about them would be read
as a clean result.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from seohead.tools.parser import robots_directives

if TYPE_CHECKING:  # pragma: no cover - typing only
    from seohead.crawl.collect import CrawlResult

# Frames a list-mode run can never fill. Declared so the analyzer skips the
# checks that depend on them instead of reporting them clean.
UNAVAILABLE_FRAMES: tuple[str, ...] = (
    "resp_4xx",
    "resp_5xx",
    "resp_3xx",
    "resp_no_response",
    "resp_blocked",
    "inlinks_4xx",
    "inlinks_5xx",
    "inlinks_3xx",
    "all_inlinks",
    "sitemap_in",
    "sitemap_not_in",
    "sitemap_orphan",
    "sitemap_non_indexable",
    "sitemap_redirects",
    "sitemap_non_200",
    "images_missing_alt",
    "images_over_kb",
    "images_missing_size",
    "titles_duplicate",
    "titles_multiple",
    "hreflang",
    "all_hreflang",
    "desc_duplicate",
    "redirect_chains",
    "crawl_overview",
    "security_mixed",
    "security_hsts",
    "structured_data_missing",
)

# Evidence a list-mode run cannot measure at all. Emitting an empty column would
# let a length or similarity check read it as zero.
UNMEASURED_COLUMNS: tuple[str, ...] = (
    "Title 1 Pixel Width",
    "Meta Description 1 Pixel Width",
    "Readability",
    "Flesch Reading Ease Score",
    "Closest Similarity Match",
    "No. Near Duplicates",
    "Link Score",
    "Spelling Errors",
    "Grammar Errors",
)


def _indexability(record: Any) -> tuple[str, str]:
    """Derive SF's Indexability pair without inventing a verdict."""
    if record.error and record.status_code is None:
        return "Non-Indexable", "Response unavailable"
    code = record.status_code
    if code is None:
        return "Non-Indexable", "Response unavailable"
    if 300 <= code < 400:
        return "Non-Indexable", "Redirected"
    if code >= 400:
        return "Non-Indexable", "Client Error" if code < 500 else "Server Error"
    directives = robots_directives(record.meta_robots, record.x_robots)
    if "noindex" in directives:
        return "Non-Indexable", "noindex"
    if record.canonical and record.canonical.rstrip("/") != record.url.rstrip("/"):
        return "Non-Indexable", "Canonicalised"
    return "Indexable", ""


def _row(record: Any) -> dict[str, Any]:
    indexability, reason = _indexability(record)
    return {
        "Address": record.url,
        "Content Type": record.content_type,
        "Status Code": record.status_code if record.status_code is not None else 0,
        "Status": record.error or ("OK" if record.status_code == 200 else ""),
        "Indexability": indexability,
        "Indexability Status": reason,
        "Title 1": record.title,
        "Title 1 Length": len(record.title),
        "Meta Description 1": record.meta_description,
        "Meta Description 1 Length": len(record.meta_description),
        "H1-1": record.h1,
        "H1-1 Length": len(record.h1),
        "H1-2": record.h1_2,
        "H2-1": record.h2,
        "Canonical Link Element 1": record.canonical,
        "Meta Robots 1": record.meta_robots,
        "X-Robots-Tag 1": record.x_robots,
        "OG:Title": record.og_title,
        "OG:Description": record.og_description,
        "OG:Image": record.og_image,
        "Size (bytes)": record.size_bytes,
        "Word Count": record.word_count,
        "Text Ratio": record.text_ratio if record.text_ratio is not None else "",
        # The collector counts every link it found; this column counts internal
        # links only, and External Outlinks is the disjoint remainder.
        "Outlinks": max(record.outlinks - record.external_outlinks, 0),
        "External Outlinks": record.external_outlinks,
        "Response Time": record.response_time if record.response_time is not None else "",
        "Redirect URL": record.redirect_url,
        "Crawl Depth": record.crawl_depth,
        "Structured Data": record.jsonld_blocks_found,
        # Not an SF column; seohead.sf.core.normalize resolves it only for
        # this collector's own frames (#18). "static" unless selective
        # rendering escalation re-fetched this page under a fuller
        # representation -- see seohead.crawl.render_escalation.
        "Representation": record.representation,
    }


def build_evidence(result: CrawlResult) -> dict[str, Any]:
    """Project a crawl into analyzer-shaped frames with its gaps declared.

    Returns plain data — frames, found, missing — rather than an analyzer type.
    The module boundary is the point: ``seohead.crawl`` must stay importable and
    testable without ``seohead.sf``, so assembling the contract is the caller's
    job and the two packages never import each other.
    """
    import pandas as pd

    frame = pd.DataFrame([_row(record) for record in result.pages])
    return {
        "frames": {"internal_all": frame},
        "found": ["internal_all"],
        "missing": list(UNAVAILABLE_FRAMES),
        "unmeasured_columns": list(UNMEASURED_COLUMNS),
    }
