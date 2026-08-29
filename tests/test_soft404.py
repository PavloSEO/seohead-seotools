"""Network-independent soft-404 tests for ``probe_urls`` and classification."""

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
