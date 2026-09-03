"""Guardrails: which addresses are reachable, and how directives are obeyed."""

import pytest

from seohead.crawl.spider import crawl_site
from seohead.recon.net import _is_public_address
from seohead.tools.robots import _rules_for, crawl_delay, parse_robots


class FakeResponse:
    def __init__(self, text="", status_code=200, ct="text/html"):
        self.text = text
        self.status_code = status_code
        self.headers = {"content-type": ct}


def page(*links, title="t"):
    body = "".join(f'<a href="{h}">x</a>' for h in links)
    return FakeResponse(
        f"<html><head><title>{title}</title></head><body><h1>H</h1>{body}</body></html>"
    )


# ── address guard ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "address,expected",
    [
        ("8.8.8.8", True),
        ("2001:4860:4860::8888", True),
        ("10.0.0.5", False),
        ("127.0.0.1", False),
        ("169.254.169.254", False),
        ("::ffff:127.0.0.1", False),
        # A non-public address wrapped in a globally-scoped one. Python's
        # is_global answers a question about the address family, not about
        # where the packet ends up.
        ("64:ff9b::7f00:1", False),  # NAT64 -> 127.0.0.1
        ("64:ff9b::a00:5", False),  # NAT64 -> 10.0.0.5
        ("64:ff9b::a9fe:a9fe", False),  # NAT64 -> cloud metadata
        ("64:ff9b:1::a9fe:a9fe", False),  # local-use NAT64 prefix
        ("2002:7f00:1::", False),  # 6to4 -> 127.0.0.1
        # The same wrappers around a genuinely public address stay allowed.
        ("64:ff9b::808:808", True),  # NAT64 -> 8.8.8.8
        ("2002:0808:0808::", True),  # 6to4 -> 8.8.8.8
    ],
)
def test_translated_addresses_are_judged_by_where_they_land(address, expected):
    assert _is_public_address(address) is expected


def test_a_malformed_address_is_not_public():
    assert _is_public_address("not-an-address") is False


# ── robots parsing ──────────────────────────────────────────────────────────

ROBOTS = """
User-agent: *
Crawl-delay: 2.5
Disallow: /private/

User-agent: Googlebot
Disallow: /nogoogle/

User-agent: SEOHEAD-Tools
Disallow: /ours/
"""


def test_crawl_delay_is_parsed():
    assert crawl_delay(parse_robots(ROBOTS)) == 2.5


def test_a_malformed_crawl_delay_is_ignored_rather_than_fatal():
    assert crawl_delay(parse_robots("User-agent: *\nCrawl-delay: soon\n")) is None


def test_a_comma_decimal_crawl_delay_is_understood():
    assert crawl_delay(parse_robots("User-agent: *\nCrawl-delay: 1,5\n")) == 1.5


def test_the_most_specific_group_wins_not_the_last_one():
    parsed = parse_robots(ROBOTS)
    assert _rules_for(parsed, "SEOHEAD-Tools")["disallow"] == ["/ours/"]
    assert _rules_for(parsed, "Googlebot")["disallow"] == ["/nogoogle/"]


def test_a_token_matches_a_more_specific_agent_but_not_the_reverse():
    parsed = parse_robots(ROBOTS)
    assert _rules_for(parsed, "Googlebot-Image")["disallow"] == ["/nogoogle/"]


def test_a_token_appearing_mid_string_no_longer_claims_the_agent():
    """Substring matching let any group whose token appeared anywhere win.

    The function takes a product token, and a token must be a prefix of it —
    "bot" must not capture "SEOHEAD-Tools" merely by occurring inside a name.
    """
    parsed = parse_robots("User-agent: Tools\nDisallow: /\n\nUser-agent: *\nDisallow: /private/\n")
    assert _rules_for(parsed, "SEOHEAD-Tools")["disallow"] == ["/private/"]


def test_an_unknown_agent_falls_back_to_the_wildcard_group():
    assert _rules_for(parse_robots(ROBOTS), "SomeOtherBot")["disallow"] == ["/private/"]


# ── policy in the spider ────────────────────────────────────────────────────

SITE = {
    "https://example.com/robots.txt": FakeResponse(
        "User-agent: *\nCrawl-delay: 3\nDisallow: /private/\n", ct="text/plain"
    ),
    "https://example.com/": page("/a", "/private/secret"),
    "https://example.com/a": page(),
    "https://example.com/private/secret": page(),
}


def _crawl(policy, site=None, **kw):
    mapping = site or SITE
    return crawl_site(
        "https://example.com/",
        robots_policy=policy,
        min_delay=0,
        sleeper=lambda _s: None,
        fetcher=lambda u: mapping.get(u) or FakeResponse("", 404),
        **kw,
    )


def test_respect_does_not_fetch_disallowed_urls():
    result = _crawl("respect")
    assert "https://example.com/private/secret" not in {p.url for p in result.pages}
    assert result.excluded.get("blocked_by_robots") == 1


def test_report_only_crawls_the_url_and_still_reports_it_as_blocked():
    """Full coverage plus an inventory of what a compliant crawler would miss."""
    result = _crawl("report_only")
    assert "https://example.com/private/secret" in {p.url for p in result.pages}
    assert result.robots_blocked == ["https://example.com/private/secret"]
    assert "blocked_by_robots" not in result.excluded


def test_ignore_does_not_fetch_the_file_so_it_reports_nothing():
    result = _crawl("ignore")
    assert "https://example.com/private/secret" in {p.url for p in result.pages}
    assert result.robots_blocked == []
    assert "not fetched" in result.robots_note


def test_a_stated_crawl_delay_raises_the_floor():
    result = _crawl("respect")
    assert result.crawl_delay_applied == 3.0
    assert result.effective_delay >= 3.0


def test_a_configured_delay_higher_than_the_stated_one_is_kept():
    """The site's request is a floor on politeness, never a ceiling."""
    result = crawl_site(
        "https://example.com/",
        robots_policy="respect",
        min_delay=10.0,
        sleeper=lambda _s: None,
        fetcher=lambda u: SITE.get(u) or FakeResponse("", 404),
    )
    assert result.effective_delay >= 10.0


def test_a_delay_is_not_applied_when_robots_is_not_fetched():
    assert _crawl("ignore").crawl_delay_applied is None
