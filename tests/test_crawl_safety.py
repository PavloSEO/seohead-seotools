"""Guardrails: which addresses are reachable, and how directives are obeyed."""

import pytest

from seohead.crawl.collect import collect_urls, fetch_one
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


# ── pinned transport ────────────────────────────────────────────────────────


def test_a_request_is_pinned_to_the_address_that_was_vetted():
    """Resolving twice leaves a window between the check and the connection."""
    from seohead.recon.net import pinned_target

    url, headers, extensions = pinned_target("https://example.com/path?a=1")
    assert headers["Host"] == "example.com"
    assert extensions["sni_hostname"] == "example.com"
    assert "example.com" not in url  # the connection goes to an address
    assert url.endswith("/path?a=1")


def test_pinning_preserves_a_non_default_port():
    from seohead.recon.net import pinned_target

    url, headers, _ = pinned_target("https://example.com:8443/")
    assert headers["Host"] == "example.com:8443"
    assert url.endswith(":8443/")


def test_pinning_refuses_a_url_without_a_host():
    from seohead.recon.net import pinned_target

    with pytest.raises(ValueError, match="no host"):
        pinned_target("file:///etc/passwd")


def test_pinning_refuses_a_private_target():
    from seohead.recon.net import pinned_target

    with pytest.raises(ValueError):
        pinned_target("http://127.0.0.1:8080/")


def test_pinning_honours_the_named_host_allowlist_but_not_a_different_host(monkeypatch):
    """The connection path itself (not just validate_url) respects the scoped opt-in."""
    from seohead.recon import net

    records = [(net.socket.AF_INET, net.socket.SOCK_STREAM, 6, "", ("10.0.0.9", 443))]
    monkeypatch.setattr(net.socket, "getaddrinfo", lambda *_a, **_k: records)
    monkeypatch.delenv(net.PRIVATE_NETWORK_ENV, raising=False)
    monkeypatch.setenv(net.PRIVATE_HOST_ALLOWLIST_ENV, "staging.internal")

    url, headers, _ = net.pinned_target("https://staging.internal/")
    assert headers["Host"] == "staging.internal"
    assert "10.0.0.9" in url

    with pytest.raises(ValueError):
        net.pinned_target("https://other-internal.example/")


# ── circuit breaker ─────────────────────────────────────────────────────────


def test_a_single_429_is_treated_as_an_overload_signal():
    from seohead.crawl.throttle import Throttle

    t = Throttle(min_delay=0.5)
    before = t.delay
    t.record_server_error(429)
    assert t.delay > before * 2


def test_retry_after_raises_the_delay_to_at_least_what_was_asked():
    from seohead.crawl.throttle import Throttle

    t = Throttle(min_delay=0.5)
    t.record_server_error(503, retry_after=30.0)
    assert t.delay >= 30.0


def test_a_non_numeric_retry_after_is_not_mistaken_for_a_duration():
    from seohead.crawl.collect import _retry_after

    assert _retry_after("Wed, 21 Oct 2026 07:28:00 GMT") is None
    assert _retry_after("120") == 120.0
    assert _retry_after(None) is None


def test_repeated_server_refusals_stop_the_crawl():
    site = {
        "https://example.com/robots.txt": FakeResponse("User-agent: *\n", ct="text/plain"),
        "https://example.com/": page(*[f"/p{i}" for i in range(9)]),
    }
    for i in range(9):
        site[f"https://example.com/p{i}"] = FakeResponse("", status_code=503)
    result = crawl_site(
        "https://example.com/",
        min_delay=0,
        sleeper=lambda _s: None,
        fetcher=lambda u: site.get(u) or FakeResponse("", 404),
        max_urls=50,
    )
    assert result.partial is True
    assert "refused repeatedly" in result.stopped_reason


def test_a_success_clears_the_refusal_streak():
    from seohead.crawl.throttle import Throttle

    t = Throttle()
    for _ in range(4):
        t.record_server_error(503)
    t.record_success()
    assert t.host_is_failing() is False


# ── concurrency ceiling (#14: "a config file alone cannot raise it") ────────


def test_the_concurrency_ceiling_is_enforced_by_the_throttle_itself_not_only_by_a_caller():
    """A config-supplied value is clamped at the object that actually paces
    requests, not only where the caller happens to validate it — so a future
    caller that constructs a Throttle directly, without going through
    crawl_site()'s own clamp, still cannot exceed the ceiling."""
    from seohead.crawl.throttle import MAX_CONCURRENCY_CEILING, Throttle

    t = Throttle(max_concurrency=999)
    assert t.max_concurrency == MAX_CONCURRENCY_CEILING


def test_the_configured_concurrency_ceiling_survives_a_crawl_end_to_end():
    """The obvious bypass: ask crawl_site() itself for far more than the ceiling."""
    from seohead.crawl.throttle import MAX_CONCURRENCY_CEILING

    site = {
        "https://example.com/robots.txt": FakeResponse("User-agent: *\n", ct="text/plain"),
        "https://example.com/": page(*[f"/p{i}" for i in range(30)]),
        **{f"https://example.com/p{i}": page() for i in range(30)},
    }
    result = crawl_site(
        "https://example.com/",
        min_delay=0,
        sleeper=lambda _s: None,
        fetcher=lambda u: site.get(u) or FakeResponse("", 404),
        max_urls=50,
        concurrency=999,
    )
    assert result.effective_concurrency <= MAX_CONCURRENCY_CEILING


# ── credential headers ──────────────────────────────────────────────────────


def test_fetch_one_sends_credential_headers_through_the_real_client(monkeypatch):
    """extra_headers must reach the request, not just be accepted and dropped."""
    import seohead.crawl.collect as collect_mod

    monkeypatch.setattr(collect_mod, "validate_url", lambda u: u)
    monkeypatch.setattr(
        collect_mod,
        "pinned_target",
        lambda u: (u, {"Host": "example.com"}, {"sni_hostname": "example.com"}),
    )
    captured = {}

    class FakeClient:
        def get(self, target, *, headers, extensions):
            captured["headers"] = headers
            return FakeResponse("<html><head><title>t</title></head><body></body></html>")

    record, _ = fetch_one(
        "https://example.com/",
        client=FakeClient(),
        extra_headers={"Authorization": "Bearer secret-token"},
    )
    assert captured["headers"]["Authorization"] == "Bearer secret-token"
    assert record.status_code == 200


def test_the_spider_resolves_credentials_per_hop_by_that_hops_own_host(monkeypatch):
    """A stale host from an earlier hop must never decide a later request's headers."""
    import seohead.crawl.spider as spider_mod

    seen_hosts = []
    monkeypatch.setattr(
        spider_mod,
        "resolve_credential_headers",
        lambda entries, host: seen_hosts.append(host) or {},
    )
    site = {
        "https://example.com/robots.txt": FakeResponse("User-agent: *\n", ct="text/plain"),
        "https://example.com/": page("/a"),
        "https://example.com/a": page(),
    }
    crawl_site(
        "https://example.com/",
        min_delay=0,
        sleeper=lambda _s: None,
        fetcher=lambda u: site.get(u) or FakeResponse("", 404),
        credential_headers=[{"host": "example.com", "headers": {}}],
    )
    assert seen_hosts == ["example.com", "example.com"]


def test_list_mode_never_resolves_one_hosts_credentials_for_another(monkeypatch):
    """The direct shape of "dropped on cross-host redirect": a list crawl can name
    URLs on several hosts, and a credential bound to one must not follow to another.
    """
    import seohead.crawl.collect as collect_mod

    seen_hosts = []
    monkeypatch.setattr(
        collect_mod,
        "resolve_credential_headers",
        lambda entries, host: seen_hosts.append(host) or {},
    )
    collect_urls(
        ["https://a.example.com/", "https://b.example.com/"],
        min_delay=0,
        sleeper=lambda _s: None,
        fetcher=lambda _u: page(),
        credential_headers=[{"host": "a.example.com", "headers": {}}],
    )
    assert seen_hosts == ["a.example.com", "b.example.com"]
