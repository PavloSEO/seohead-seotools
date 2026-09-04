"""Every key under scope must change what a crawl fetches.

A setting that is validated, recorded in the run manifest, and then read by
nothing is worse than a missing feature: it reports that it took effect.
"""

from __future__ import annotations

import pytest

from seohead.crawl.settings import ConfigError, load, validate
from seohead.crawl.spider import Scope, crawl_site
from tests.test_crawl_spider import FakeResponse, _fetcher, page

SITE = {
    "https://example.com/robots.txt": FakeResponse(
        "User-agent: *\nDisallow:\n", headers={"content-type": "text/plain"}
    ),
    "https://example.com/": page("/blog/post", "/assets/img/logo.jpg", "/shop/item"),
    "https://example.com/blog/post": page(),
    "https://example.com/assets/img/logo.jpg": page(),
    "https://example.com/shop/item": page(),
}

SUBDOMAIN_SITE = {
    "https://example.com/robots.txt": FakeResponse(
        "User-agent: *\nDisallow:\n", headers={"content-type": "text/plain"}
    ),
    "https://shop.example.com/robots.txt": FakeResponse(
        "User-agent: *\nDisallow:\n", headers={"content-type": "text/plain"}
    ),
    "https://example.com/": page("https://shop.example.com/x", "https://other.com/y"),
    "https://shop.example.com/x": page(),
}


def _crawl(mapping, **kw):
    kw.setdefault("sleeper", lambda _s: None)
    kw.setdefault("min_delay", 0)
    return crawl_site("https://example.com/", fetcher=_fetcher(mapping), **kw)


def _urls(result) -> set[str]:
    return {p.url for p in result.pages}


def _fetched(result, url: str) -> bool:
    """Exact-match membership: a URL was fetched or it was not."""
    return any(page.url == url for page in result.pages)


# --- exclude_patterns -------------------------------------------------------
def test_exclude_patterns_keep_assets_out_of_the_budget():
    result = _crawl(SITE, scope={"exclude_patterns": [r"\.jpg$", "/assets/"]})
    assert not _fetched(result, "https://example.com/assets/img/logo.jpg")
    assert _fetched(result, "https://example.com/blog/post")
    assert result.excluded.get("excluded_by_pattern") == 1


def test_without_exclude_patterns_assets_are_fetched():
    # The behaviour the setting is supposed to change.
    assert _fetched(_crawl(SITE), "https://example.com/assets/img/logo.jpg")


# --- include_patterns -------------------------------------------------------
def test_include_patterns_restrict_the_crawl():
    result = _crawl(SITE, scope={"include_patterns": ["/blog/"]})
    assert _urls(result) == {"https://example.com/", "https://example.com/blog/post"}
    assert result.excluded.get("not_included_by_pattern") == 2


def test_the_seed_is_fetched_even_when_it_matches_no_include_pattern():
    # Otherwise a filtered crawl reports an empty site rather than a mistake.
    result = _crawl(SITE, scope={"include_patterns": ["/blog/"]})
    assert _fetched(result, "https://example.com/")


# --- scope.internal ---------------------------------------------------------
def test_host_scope_excludes_subdomains():
    result = _crawl(SUBDOMAIN_SITE)
    assert not _fetched(result, "https://shop.example.com/x")


def test_registrable_domain_scope_includes_subdomains():
    result = _crawl(SUBDOMAIN_SITE, scope={"internal": "registrable_domain"})
    assert _fetched(result, "https://shop.example.com/x")
    assert not _fetched(result, "https://other.com/y")


# --- exclude_hosts ----------------------------------------------------------
def test_exclude_hosts_wins_over_a_widened_scope():
    result = _crawl(
        SUBDOMAIN_SITE,
        scope={"internal": "registrable_domain", "exclude_hosts": ["shop.example.com"]},
    )
    assert not _fetched(result, "https://shop.example.com/x")
    assert result.excluded.get("excluded_host") == 1


# --- configuration ----------------------------------------------------------
def test_a_pattern_that_does_not_compile_is_rejected_before_the_crawl():
    # A crawl must not fail on its three-hundredth URL over a typo in a setting.
    with pytest.raises(ConfigError, match="not a valid regex"):
        load(overrides={"scope.exclude_patterns": ["["]})


def test_a_valid_pattern_passes_validation():
    config = load(overrides={"scope.exclude_patterns": [r"\.jpg$"]})
    assert config["scope"]["exclude_patterns"] == [r"\.jpg$"]
    validate(config)


def test_scope_reads_an_absent_config_as_the_default():
    assert Scope.from_config(None) == Scope()
