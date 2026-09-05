"""Network-independent soft-404 tests for ``probe_urls`` and classification."""

from seohead.recon import net as recon_net
from seohead.recon.net import BlockedRedirectError
from seohead.tools import soft404 as S


def test_probe_urls_deterministic_per_origin():
    a = S.probe_urls("https://shop.example.com/page")
    b = S.probe_urls("https://shop.example.com/other")
    assert a == b, "probes are deterministic by origin, not by path"
    assert len(a) == S.PROBE_COUNT
    assert all(".well-known/seo-audit/not-found-" in u for u in a)


def test_probe_urls_differ_per_origin():
    a = S.probe_urls("https://shop.example.com")
    b = S.probe_urls("https://other.example.org")
    assert a != b


def test_classify_pass_when_both_404():
    probes = [{"status": 404}, {"status": 410}]
    assert S.classify_soft404(probes) == "pass"


def test_classify_warning_when_both_200():
    probes = [{"status": 200}, {"status": 301, "final_url": "x"}]
    assert S.classify_soft404(probes) == "warning"


def test_classify_unknown_on_mixed():
    probes = [{"status": 200}, {"status": 404}]
    assert S.classify_soft404(probes) == "unknown"


def test_classify_unknown_when_probe_errored():
    probes = [{"status": 404}, {"error": "timeout"}]
    assert S.classify_soft404(probes) == "unknown"


def test_classify_respects_access_blocked():
    probes = [{"status": 404}, {"status": 200, "access_blocked": True}]
    # With only one conclusive probe, the result must remain unknown.
    assert S.classify_soft404(probes) == "unknown"


def test_classify_refused_when_a_probe_was_blocked_by_our_own_guard():
    """#175: a guard refusal is not the same fact as "the probes disagreed"."""
    probes = [
        {"status": 404},
        {"status": 301, "final_url": "http://169.254.169.254/", "blocked_by_guard": True},
    ]
    assert S.classify_soft404(probes) == "refused"


def test_classify_refused_takes_priority_over_a_conclusive_agreement():
    probes = [
        {"status": 404},
        {"status": 404, "blocked_by_guard": True, "final_url": "http://127.0.0.1/"},
    ]
    assert S.classify_soft404(probes) == "refused"


def test_check_soft404_records_a_guard_refusal_without_requesting_the_target(monkeypatch):
    """``check_soft404`` must classify a ``BlockedRedirectError`` the same way ``fetch_one`` does.

    ``http_client`` is monkeypatched to hand back a stub whose ``get`` raises exactly what the
    real guard raises for a redirect to a private address, so this stays a unit test of
    ``check_soft404``'s own exception handling rather than a second copy of the transport-level
    proof in ``test_redirect_guard_classification.py``.
    """
    calls: list[str] = []

    class _StubClient:
        def get(self, url):
            calls.append(url)
            raise BlockedRedirectError(
                "private or non-public network target blocked",
                status_code=301,
                location="http://169.254.169.254/",
            )

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

    monkeypatch.setattr(recon_net, "http_client", lambda timeout: (_StubClient(), True))

    result = S.check_soft404("https://shop.example.com")
    assert result["ok"] is True
    assert result["verdict"] == "refused"
    assert len(calls) == S.PROBE_COUNT
    for probe in result["probes"]:
        assert probe["blocked_by_guard"] is True
        assert probe["status"] == 301
        assert probe["final_url"] == "http://169.254.169.254/"
