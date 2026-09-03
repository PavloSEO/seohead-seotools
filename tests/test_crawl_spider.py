"""Breadth-first link discovery on a synthetic site. No network."""

import pytest

from seohead.crawl.spider import crawl_site

ROBOTS_OK = "User-agent: *\nDisallow: /private/\n"


class FakeResponse:
    def __init__(self, text="", status_code=200, headers=None):
        self.text = text
        self.status_code = status_code
        self.headers = headers or {"content-type": "text/html; charset=utf-8"}


def page(*links: str, title: str = "t") -> FakeResponse:
    """An HTML response linking to each href, in document order."""
    body = "".join(f'<a href="{href}">{href}</a>' for href in links)
    return FakeResponse(
        f"<html><head><title>{title}</title></head><body><h1>{title}</h1>{body}</body></html>"
    )


SITE = {
    "https://example.com/robots.txt": FakeResponse(
        ROBOTS_OK, headers={"content-type": "text/plain"}
    ),
    "https://example.com/": page("/a", "/b", "https://other.com/x"),
    "https://example.com/a": page("/c"),
    "https://example.com/b": page("/c"),
    "https://example.com/c": page(),
    "https://example.com/private/secret": page(),
}


def _fetcher(mapping):
    def fetch(url):
        value = mapping.get(url)
        if value is None:
            return FakeResponse("", status_code=404)
        if isinstance(value, Exception):
            raise value
        return value

    return fetch


def _crawl(mapping=None, **kw):
    kw.setdefault("sleeper", lambda _s: None)
    kw.setdefault("min_delay", 0)
    return crawl_site("https://example.com/", fetcher=_fetcher(mapping or SITE), **kw)


def test_follows_links_and_finds_the_whole_site():
    result = _crawl()
    found = {p.url for p in result.pages}
    assert found == {
        "https://example.com/",
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    }


def test_visits_each_url_once_even_when_linked_twice():
    result = _crawl()
    urls = [p.url for p in result.pages]
    assert len(urls) == len(set(urls))


def test_external_links_are_recorded_but_never_fetched():
    result = _crawl()
    assert "https://other.com/x" not in {p.url for p in result.pages}
    assert any(edge.destination == "https://other.com/x" for edge in result.links)
    assert result.excluded.get("outside_host", 0) >= 1


def test_depth_is_recorded_and_bounded():
    result = _crawl(max_depth=1)
    depths = {p.url: p.crawl_depth for p in result.pages}
    assert depths["https://example.com/"] == 0
    assert depths["https://example.com/a"] == 1
    assert "https://example.com/c" not in depths
    assert result.excluded.get("depth_limit", 0) >= 1


def test_robots_disallow_is_honoured():
    site = dict(SITE)
    site["https://example.com/"] = page("/a", "/private/secret")
    result = _crawl(site)
    assert "https://example.com/private/secret" not in {p.url for p in result.pages}
    assert result.excluded.get("blocked_by_robots", 0) == 1


def test_a_5xx_robots_stops_the_crawl_rather_than_allowing_it():
    """RFC 9309: an unavailable robots.txt is a full disallow."""
    site = dict(SITE)
    site["https://example.com/robots.txt"] = FakeResponse("", status_code=503)
    result = _crawl(site)
    assert result.pages == []
    assert result.partial is True
    assert "503" in result.stopped_reason


def test_the_url_budget_stops_the_crawl_and_marks_it_partial():
    result = _crawl(max_urls=2)
    assert len(result.pages) == 2
    assert result.partial is True
    assert "url limit" in result.stopped_reason


def test_traversal_is_deterministic_across_runs():
    first = [p.url for p in _crawl().pages]
    second = [p.url for p in _crawl().pages]
    assert first == second


def test_breadth_first_visits_shallow_pages_before_deep_ones():
    result = _crawl()
    depths = [p.crawl_depth for p in result.pages]
    assert depths == sorted(depths), "a BFS frontier must not descend early"


def test_a_same_host_redirect_is_followed_within_the_budget():
    site = dict(SITE)
    site["https://example.com/"] = FakeResponse(
        "",
        status_code=301,
        headers={"location": "https://example.com/a", "content-type": "text/html"},
    )
    result = _crawl(site)
    assert "https://example.com/a" in {p.url for p in result.pages}


def test_an_off_host_redirect_is_recorded_and_not_followed():
    site = dict(SITE)
    site["https://example.com/"] = FakeResponse(
        "", status_code=301, headers={"location": "https://other.com/", "content-type": "text/html"}
    )
    result = _crawl(site)
    assert "https://other.com/" not in {p.url for p in result.pages}
    assert result.excluded.get("redirect_off_host", 0) == 1


def test_repeated_timeouts_stop_the_crawl():
    """A failing origin must be left alone, not walked to the end of the queue."""
    targets = [f"/p{i}" for i in range(9)]
    site = {
        "https://example.com/robots.txt": FakeResponse(ROBOTS_OK),
        "https://example.com/": page(*targets),
    }
    for path in targets:
        site[f"https://example.com{path}"] = TimeoutError("read timed out")
    result = _crawl(site, max_urls=50)
    assert result.partial is True
    assert "timeouts" in result.stopped_reason
    assert len(result.pages) < len(targets), "must stop before exhausting the queue"


def test_the_link_graph_is_collected():
    result = _crawl()
    edges = {(e.source, e.destination) for e in result.links}
    assert ("https://example.com/", "https://example.com/a") in edges
    assert ("https://example.com/a", "https://example.com/c") in edges


@pytest.mark.parametrize("bad", ["", "not a url", "ftp:/"])
def test_a_non_crawlable_start_url_is_refused(bad):
    with pytest.raises(ValueError):
        crawl_site(bad, fetcher=_fetcher(SITE))
