"""Site-wide inlink composition from a crawl's own link graph.

Link position (see ``tools/link_position.py``) only earns its keep once it is
aggregated across a crawl: one classified link says where that one anchor
sits, but "this page is linked only from the footer, never from body copy" is
a statement about every inlink a page has, and that is a template-level
finding, not a page-level one.

This module is pure and never imports ``seohead.sf``: it works only from
``SpiderResult.links``, the collector's own evidence.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from seohead.crawl.spider import LinkEdge

# Positions that count as boilerplate for the "boilerplate only" finding.
# "other" is deliberately excluded from both this set and from counting as
# content: it means "outside a configured, narrower content area", which is
# neither a recognized boilerplate region nor confirmed content.
BOILERPLATE_POSITIONS: tuple[str, ...] = ("nav", "header", "sidebar", "footer")


def inlink_composition(links: list[LinkEdge]) -> dict[str, Any]:
    """Group a crawl's recorded links by destination and by position.

    Counts distinct (destination, source, position) triples, so a link
    repeated twice on the same page in the same position is one inlink, not
    two — the same "how many pages link here" question ``sf.core.inlinks``
    answers for Screaming Frog exports.

    Edges with no ``position`` (because the crawl did not pass
    ``classify_links=True``) are counted separately as ``edges_unclassified``
    and never folded into any bucket: a disabled classifier must read as
    "not measured", not as "no boilerplate links found".
    """
    dedup: set[tuple[str, str, str]] = set()
    by_dest: dict[str, Counter[str]] = {}
    unclassified = 0
    for edge in links:
        if not edge.position:
            unclassified += 1
            continue
        key = (edge.destination, edge.source, edge.position)
        if key in dedup:
            continue
        dedup.add(key)
        by_dest.setdefault(edge.destination, Counter())[edge.position] += 1

    pages = []
    for dest, counts in by_dest.items():
        total = sum(counts.values())
        boilerplate = sum(counts.get(p, 0) for p in BOILERPLATE_POSITIONS)
        pages.append(
            {
                "url": dest,
                "inlinks_total": total,
                "by_position": dict(sorted(counts.items())),
                # True only when every classified inlink is boilerplate (so
                # neither "content" nor "other" appears) and at least one
                # inlink was classified at all — a page with zero classified
                # inlinks is "unmeasured", not "boilerplate only".
                "boilerplate_only": bool(counts) and boilerplate == total,
            }
        )
    pages.sort(key=lambda p: p["url"])

    boilerplate_only_urls = [p["url"] for p in pages if p["boilerplate_only"]]
    findings: list[str] = []
    if boilerplate_only_urls:
        shown = ", ".join(boilerplate_only_urls[:5])
        more = (
            f" and {len(boilerplate_only_urls) - 5} more" if len(boilerplate_only_urls) > 5 else ""
        )
        findings.append(
            f"{len(boilerplate_only_urls)} page(s) are linked only from navigation, "
            f"header, sidebar, or footer — never from body content: {shown}{more}"
        )

    total_edges = len(dedup) + unclassified
    return {
        "ok": True,
        "measured": len(dedup) > 0,
        "edges_classified": len(dedup),
        "edges_unclassified": unclassified,
        "classified_fraction": round(len(dedup) / total_edges, 4) if total_edges else 0.0,
        "pages_with_inlinks": len(pages),
        "pages_boilerplate_only": boilerplate_only_urls,
        "pages": pages,
        "findings": findings,
    }
