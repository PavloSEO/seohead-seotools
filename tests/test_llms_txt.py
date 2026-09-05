"""Offline tests for the llms.txt scorer."""

from seohead.tools import llms_txt

GOOD = """# Acme Analytics Platform

> Acme helps teams understand user behavior through real-time dashboards,
> audience segments, and API reports.

## Product
- [Acme Analytics](https://example.com/product): the core analytics platform
- [Pricing](https://example.com/pricing): plans for teams of every size

## Evidence
- [Customer cases](https://example.com/cases): how Acme accelerates growth

## Documentation
- [Docs](https://example.com/docs): integration guide
- [API](https://example.com/api): API reference
"""


def test_good_llms_txt_scores_high():
    r = llms_txt.score_llms_txt(GOOD, brand="Acme")
    assert r["ok"] is True
    assert r["score"] >= 7.0
    assert r["stats"]["sections"] >= 3
    assert r["stats"]["links"] >= 3
    assert r["stats"]["mentions_brand"] is True


def test_empty_content_returns_error():
    r = llms_txt.score_llms_txt("")
    assert r["ok"] is False


def test_missing_sections_lower_score():
    bare = "# Just a title\n\nOne link [home](https://example.org).\n"
    r = llms_txt.score_llms_txt(bare, brand="X")
    assert r["score"] < 5.0
    assert r["stats"]["sections"] == 0


def test_brand_mention_check():
    r = llms_txt.score_llms_txt(GOOD, brand="Acme")
    brand_check = r["checks"][3]
    assert "Acme" in brand_check["name"]
    assert brand_check["passed"] is True


def test_h1_check_is_labeled_without_an_unverified_brand_claim():
    check = llms_txt.score_llms_txt(
        "# Unrelated heading\n\nAcme is mentioned below.", brand="Acme"
    )["checks"][0]
    assert check == {"name": "Non-empty H1 heading", "passed": True}


def test_oversized_content_fails_size_check():
    big = "# T\n\n" + ("x" * (61 * 1024))
    r = llms_txt.score_llms_txt(big)
    assert r["stats"]["size_ok"] is False
    size_check = r["checks"][-1]
    assert size_check["passed"] is False


def test_grade_thresholds():
    assert llms_txt.score_llms_txt(GOOD, brand="Acme")["grade"] in ("A", "B")
    assert llms_txt.score_llms_txt("# x\n")["grade"] in ("D", "F")


# ── A missing file is a measured result, not a tool failure ──────────────────


def test_missing_file_is_a_measured_result_not_a_tool_failure(monkeypatch):
    """A 404 means the file is absent; it must remain distinct from network failure.

    The repository invariant reserves ``ok=False`` for results that were not measured.
    """
    import seohead.recon.net as net
    from seohead.tools import llms_txt

    class _Resp:
        status_code = 404
        text = ""

    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):
            return _Resp()

    monkeypatch.setattr(net, "http_client", lambda timeout, **kw: (_Client(), False))
    r = llms_txt.check_llms_txt("https://example.com/")
    assert r["ok"] is True, "The tool completed successfully; the file is simply absent."
    assert r["exists"] is False
    assert r["score"] == 0
    assert any("llms.txt" in finding for finding in r["findings"])


def test_network_failure_still_reports_not_measured(monkeypatch):
    """A network failure stays unmeasured instead of scoring an unreachable site zero."""
    import seohead.recon.net as net
    from seohead.tools import llms_txt

    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):
            raise OSError("connection refused")

    monkeypatch.setattr(net, "http_client", lambda timeout, **kw: (_Client(), False))
    r = llms_txt.check_llms_txt("https://example.com/")
    assert r["ok"] is False and "error" in r
    assert "exists" not in r


def test_http_error_is_not_reported_as_a_missing_file(monkeypatch):
    """A received 5xx response does not establish that the manifest is absent."""
    import seohead.recon.net as net

    class _Resp:
        status_code = 500
        text = "upstream failure"

    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):
            return _Resp()

    monkeypatch.setattr(net, "http_client", lambda timeout, **kw: (_Client(), False))
    r = llms_txt.check_llms_txt("https://example.com/")
    assert r == {
        "ok": False,
        "url": "https://example.com/llms.txt",
        "status_code": 500,
        "error": "Could not measure llms.txt: HTTP 500",
    }
