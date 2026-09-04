"""Sitemap-seeded crawl mode and declared-vs-observed reconciliation. No network."""

from seohead.crawl.reconcile import reconcile_sitemap
from seohead.crawl.spider import crawl_site

ROBOTS_OK = "User-agent: *\nDisallow:\n"


class FakeResponse:
    def __init__(self, text="", status_code=200, headers=None):
        self.text = text
        self.status_code = status_code
        self.headers = headers or {"content-type": "text/html; charset=utf-8"}


def page(*links: str, title: str = "t") -> FakeResponse:
    body = "".join(f'<a href="{href}">{href}</a>' for href in links)
    return FakeResponse(
        f"<html><head><title>{title}</title></head><body><h1>{title}</h1>{body}</body></html>"
    )


def _fetcher(mapping):
    def fetch(url):
        value = mapping.get(url)
        if value is None:
            return FakeResponse("", status_code=404)
        if isinstance(value, Exception):
            raise value
        return value

    return fetch


def _crawl(mapping, **kw):
    kw.setdefault("sleeper", lambda _s: None)
    kw.setdefault("min_delay", 0)
    return crawl_site("https://example.com/", fetcher=_fetcher(mapping), **kw)


# --- unit behaviour of seed_urls ---------------------------------------------

BASE_SITE = {
    "https://example.com/robots.txt": FakeResponse(
        ROBOTS_OK, headers={"content-type": "text/plain"}
    ),
    "https://example.com/": page("/linked"),
    "https://example.com/linked": page(),
    "https://example.com/orphan": page(),
}


def test_a_seed_with_no_inbound_link_is_fetched_but_never_appears_as_a_link_target():
    result = _crawl(BASE_SITE, seed_urls=["https://example.com/orphan"])
    assert "https://example.com/orphan" in {p.url for p in result.pages}
    assert not any(e.destination == "https://example.com/orphan" for e in result.links)


def test_a_seed_that_is_also_linked_appears_both_fetched_and_as_a_link_target():
    result = _crawl(BASE_SITE, seed_urls=["https://example.com/linked"])
    assert "https://example.com/linked" in {p.url for p in result.pages}
    assert any(e.destination == "https://example.com/linked" for e in result.links)


def test_seed_urls_are_recorded_on_the_result():
    result = _crawl(BASE_SITE, seed_urls=["https://example.com/orphan"])
    assert result.seed_urls == ["https://example.com/orphan"]


def test_an_off_host_seed_is_excluded_and_never_fetched():
    result = _crawl(BASE_SITE, seed_urls=["https://other.com/x"])
    assert "https://other.com/x" not in {p.url for p in result.pages}
    assert result.excluded.get("outside_host", 0) == 1
    assert result.seed_urls == []


def test_a_seed_duplicating_the_start_url_is_not_fetched_twice():
    result = _crawl(BASE_SITE, seed_urls=["https://example.com/"])
    urls = [p.url for p in result.pages]
    assert urls.count("https://example.com/") == 1


def test_limitations_do_not_claim_no_sitemap_expansion_when_seeded():
    result = _crawl(BASE_SITE, seed_urls=["https://example.com/orphan"])
    assert "no sitemap expansion" not in result.limitations


def test_limitations_still_note_no_sitemap_expansion_without_seeding():
    result = _crawl(BASE_SITE)
    assert "no sitemap expansion" in result.limitations


# --- the acceptance-criteria fixture: 10 declared, 8 linked, 2 orphaned -----


def _fixture():
    """10 URLs declared in a sitemap: 8 linked from the home page, 2 orphaned.

    A crawled page links to one more URL ("/extra") that the sitemap never
    declares, and none of that changes just because it was reached.
    """
    linked = [f"https://example.com/p{i}" for i in range(1, 9)]
    orphaned = ["https://example.com/p9", "https://example.com/p10"]
    declared = linked + orphaned

    site = {
        "https://example.com/robots.txt": FakeResponse(
            ROBOTS_OK, headers={"content-type": "text/plain"}
        ),
        "https://example.com/": page(*linked, "/extra"),
        "https://example.com/extra": page(),
    }
    for url in linked:
        site[url] = page()
    for url in orphaned:
        site[url] = page()
    return declared, linked, orphaned, site


def test_the_fixture_places_orphans_in_their_own_set_never_merged_into_not_found():
    declared, linked, orphaned, site = _fixture()
    result = _crawl(site, seed_urls=declared)

    # Every declared URL was fetched directly, because it was seeded.
    fetched = {p.url for p in result.pages}
    assert set(declared) <= fetched

    observed = [edge.destination for edge in result.links]
    report = reconcile_sitemap(declared, observed)

    assert report["urls_in_sitemap"] == 10
    assert sorted(report["in_sitemap_and_linked"]) == sorted(linked)
    assert sorted(report["in_sitemap_not_linked"]) == sorted(orphaned)
    assert report["linked_not_in_sitemap"] == ["https://example.com/extra"]

    # The three sets are disjoint: an orphan is never also reported as missing,
    # and nothing declared-and-linked leaks into either problem set.
    healthy = set(report["in_sitemap_and_linked"])
    orphans = set(report["in_sitemap_not_linked"])
    missing = set(report["linked_not_in_sitemap"])
    assert not (healthy & orphans)
    assert not (healthy & missing)
    assert not (orphans & missing)


def test_a_url_reached_only_via_links_and_absent_from_the_sitemap_is_missing_not_an_error():
    """Reachable by crawling but not declared: reported, not treated as a fault."""
    declared, _linked, _orphaned, site = _fixture()
    result = _crawl(site, seed_urls=declared)
    observed = [edge.destination for edge in result.links]
    report = reconcile_sitemap(declared, observed)
    assert "https://example.com/extra" in report["linked_not_in_sitemap"]
