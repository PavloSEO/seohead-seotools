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


def reconcile_sitemap(
    declared: Iterable[str],
    observed: Iterable[str],
    comparable: Iterable[str] | None = None,
) -> dict[str, object]:
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

    ``comparable`` is the subset of the crawl a sitemap is actually supposed to describe:
    fetched, same-host, HTML, indexable. It exists because the two questions here need two
    different populations. "Nothing links to this declared URL" is a claim about reachability,
    so it is asked against every link destination — narrowing that side would invent orphans.
    "This page is missing from the sitemap" is a claim about pages, so asking it against every
    link destination reports images, off-host links and URLs the crawl never fetched; on one
    live 124-page site that produced 392 findings, 74% of the whole report (issue #94).

    When ``comparable`` is given, ``linked_not_in_sitemap`` is drawn from it, and everything
    reachable but outside it is returned separately as ``linked_not_comparable`` rather than
    silently dropped — a link to an image is a fact about the site, just not a sitemap defect.
    When it is ``None`` the caller has no such classification and every observed URL is treated
    as comparable, which is the original behaviour.
    """
    declared_set = _normalized_set(declared)
    observed_set = _normalized_set(observed)
    comparable_set = observed_set if comparable is None else _normalized_set(comparable)
    # A URL can only be judged against the sitemap if the crawl actually reached it by a link;
    # anything else in the caller's comparable population was not observed and says nothing.
    comparable_set &= observed_set

    healthy = sorted(declared_set & observed_set)
    orphaned = sorted(declared_set - observed_set)
    missing_from_sitemap = sorted(comparable_set - declared_set)
    not_comparable = sorted(observed_set - comparable_set - declared_set)

    return {
        "urls_in_sitemap": len(declared_set),
        "urls_reached_by_links": len(observed_set),
        "in_sitemap_and_linked": healthy,
        "in_sitemap_not_linked": orphaned,
        "linked_not_in_sitemap": missing_from_sitemap,
        # Reachable, but not the kind of URL a sitemap of pages is supposed to declare:
        # off-host, non-HTML, non-indexable, or never fetched. Named, not discarded.
        "linked_not_comparable": not_comparable,
        # Count aliases matching the Screaming Frog pipeline's own summary
        # (seohead.sf.core.sitemap_coverage.run_sitemap), so a consumer reading counts
        # out of audit.json's summary.sitemap need not branch on crawl mode.
        "in_sitemap_not_in_crawl": len(orphaned),
        "in_crawl_not_in_sitemap": len(missing_from_sitemap),
    }
