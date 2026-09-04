"""Declared-vs-observed reconciliation between a sitemap and a crawl's link graph.

A sitemap and a crawl are two independent claims about which pages exist. Naming
the disagreement is the entire value: a URL the sitemap declares but no page ever
links to is orphaned (indexable, but invisible to internal navigation); a URL the
crawl finds by following links but the sitemap never mentions is either a stale
sitemap or a deliberate exclusion. Merging either of those into a generic
"not found" bucket would erase the distinction that makes this diagnostic worth
running, so this module always returns three disjoint sets and never collapses
them into two.

Pure and network-free: callers do the fetching (``seohead.tools.sitemap.crawl``
for the declared set, the spider's own link graph for the observed set) and hand
plain URL lists here.
"""

from __future__ import annotations

from collections.abc import Iterable

from seohead.tools.sitemap import normalize_url

__all__ = ["reconcile_sitemap"]


def _normalized_set(urls: Iterable[str]) -> set[str]:
    out: set[str] = set()
    for url in urls:
        if not url:
            continue
        try:
            out.add(normalize_url(url))
        except ValueError:
            continue  # not an absolute URL; cannot be compared, so it is dropped
    return out


def reconcile_sitemap(declared: Iterable[str], observed: Iterable[str]) -> dict[str, object]:
    """Compare a sitemap's declared URLs against a crawl's link-graph reachability.

    ``declared`` is the sitemap's own URL set (e.g. from ``sitemap.crawl()``).
    ``observed`` is every URL the crawl found by following a link — not merely
    every URL it fetched, since a sitemap-seeded crawl fetches its seeds
    directly regardless of whether anything links to them. Reachability, not
    fetch status, is what distinguishes an orphan from a healthy page.

    Returns three disjoint URL lists, each reported under its own honest name:

    * ``in_sitemap_and_linked`` — declared and reachable by following links.
    * ``in_sitemap_not_linked`` — declared, but no crawled page links to it
      (orphaned: indexable, invisible to internal navigation).
    * ``linked_not_in_sitemap`` — reachable by following links, but not declared
      (a stale sitemap, or a deliberate exclusion worth confirming).
    """
    declared_set = _normalized_set(declared)
    observed_set = _normalized_set(observed)

    healthy = sorted(declared_set & observed_set)
    orphaned = sorted(declared_set - observed_set)
    missing_from_sitemap = sorted(observed_set - declared_set)

    return {
        "urls_in_sitemap": len(declared_set),
        "urls_reached_by_links": len(observed_set),
        "in_sitemap_and_linked": healthy,
        "in_sitemap_not_linked": orphaned,
        "linked_not_in_sitemap": missing_from_sitemap,
        # Count aliases matching the Screaming Frog pipeline's own summary
        # (seohead.sf.core.sitemap.run_sitemap), so a consumer reading counts
        # out of audit.json's summary.sitemap need not branch on crawl mode.
        "in_sitemap_not_in_crawl": len(orphaned),
        "in_crawl_not_in_sitemap": len(missing_from_sitemap),
    }
