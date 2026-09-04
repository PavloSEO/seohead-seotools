"""The handler layer wires the crawl config into the collector and back into
the audit — this is where a checkpoint path, a duration budget, and a finish
reason actually reach the crawler and the report. No network: the crawler
itself is replaced with a fake."""

import json

import seohead.crawl.spider as spider_mod
from seohead.crawl.collect import PageRecord
from seohead.crawl.spider import LinkEdge, SpiderResult
from seohead.servers import handlers


def test_out_dir_derives_a_state_path_and_a_config_fingerprint(tmp_path, monkeypatch):
    captured = {}

    def fake(*args, **kwargs):
        captured.update(kwargs)
        return SpiderResult()

    monkeypatch.setattr(spider_mod, "crawl_site", fake)

    handlers.crawl_site(url="https://example.com/", out_dir=str(tmp_path))

    assert captured["state_path"] == str(tmp_path / "crawl_state.json")
    assert isinstance(captured["config_fingerprint"], str) and captured["config_fingerprint"]
    assert captured["max_seconds"] == 0


def test_no_out_dir_means_no_state_path(monkeypatch):
    captured = {}

    def fake(*args, **kwargs):
        captured.update(kwargs)
        return SpiderResult()

    monkeypatch.setattr(spider_mod, "crawl_site", fake)
    handlers.crawl_site(url="https://example.com/")
    assert captured["state_path"] is None


def test_finish_reason_and_resumed_reach_the_handler_output(monkeypatch):
    def fake(*args, **kwargs):
        result = SpiderResult()
        result.finish_reason = "url_limit"
        result.partial = True
        result.resumed = True
        return result

    monkeypatch.setattr(spider_mod, "crawl_site", fake)
    out = handlers.crawl_site(url="https://example.com/")
    assert out["finish_reason"] == "url_limit"
    assert out["resumed"] is True
    assert out["partial"] is True


def test_cache_replay_and_stats_reach_the_handler_output_and_the_audit_manifest(
    tmp_path, monkeypatch
):
    """A cached-partly report must say so, both in the immediate result and in audit.json —
    'the site is fine' and 'the site was fine last time we looked' are different claims."""

    def fake(*args, **kwargs):
        result = SpiderResult()
        result.cache_replay = True
        result.cache_stats = {
            "hits": 3,
            "revalidations": 1,
            "stores": 0,
            "bypassed": 0,
            "invalidated": 0,
        }
        return result

    monkeypatch.setattr(spider_mod, "crawl_site", fake)
    out = handlers.crawl_site(url="https://example.com/", out_dir=str(tmp_path))

    assert out["cache_replay"] is True
    assert out["cache_stats"]["hits"] == 3

    audit = json.loads((tmp_path / "audit.json").read_text())
    assert audit["run"]["cache_replay"] is True
    assert audit["run"]["cache_stats"]["revalidations"] == 1


def test_with_no_cache_configured_the_handler_output_says_so_plainly(monkeypatch):
    def fake(*args, **kwargs):
        return SpiderResult()

    monkeypatch.setattr(spider_mod, "crawl_site", fake)
    out = handlers.crawl_site(url="https://example.com/")
    assert out["cache_replay"] is False
    assert out["cache_stats"] == {}


def test_cache_mode_off_by_default_means_the_spider_receives_no_cache_object(monkeypatch):
    """The default must not create any cache — see the settings-level test for why."""
    captured = {}

    def fake(*args, **kwargs):
        captured.update(kwargs)
        return SpiderResult()

    monkeypatch.setattr(spider_mod, "crawl_site", fake)
    handlers.crawl_site(url="https://example.com/")
    assert captured["cache"] is None


# ── Pre-flight rendering gate (#18) ──────────────────────────────────────────


def _fake_spider_with_start_page(outlinks, external_outlinks, html):
    start = PageRecord(
        url="https://example.com/", outlinks=outlinks, external_outlinks=external_outlinks
    )

    def fake(*args, **kwargs):
        result = SpiderResult()
        result.pages = [start]
        result.start_page_evidence = {
            "html": html,
            "outlinks": outlinks,
            "external_outlinks": external_outlinks,
        }
        return result

    return fake


def test_zero_internal_links_on_the_start_page_requires_rendering(monkeypatch):
    fake = _fake_spider_with_start_page(0, 0, "<html><body>hi</body></html>")
    monkeypatch.setattr(spider_mod, "crawl_site", fake)
    out = handlers.crawl_site(url="https://example.com/")
    assert out["requires_rendering"] is True
    assert "zero internal links" in out["requires_rendering_reason"]
    assert out["summary"]["health_score"] is None


def test_an_empty_spa_shell_on_the_start_page_requires_rendering(monkeypatch):
    html = '<html><body><div id="root"></div></body></html>'
    fake = _fake_spider_with_start_page(3, 0, html)
    monkeypatch.setattr(spider_mod, "crawl_site", fake)
    out = handlers.crawl_site(url="https://example.com/")
    assert out["requires_rendering"] is True
    assert "empty SPA shell" in out["requires_rendering_reason"]


def test_a_normal_start_page_does_not_require_rendering(monkeypatch):
    fake = _fake_spider_with_start_page(5, 0, "<html><body>hi there</body></html>")
    monkeypatch.setattr(spider_mod, "crawl_site", fake)
    out = handlers.crawl_site(url="https://example.com/")
    assert out["requires_rendering"] is False
    assert out["requires_rendering_reason"] == ""


def test_the_gate_applies_even_in_the_default_raw_mode(monkeypatch):
    """Both checks are static-only, so the default (no rendering ever configured)
    still catches the false-green case #18 exists for."""
    fake = _fake_spider_with_start_page(0, 0, "<html></html>")
    monkeypatch.setattr(spider_mod, "crawl_site", fake)
    out = handlers.crawl_site(url="https://example.com/")
    assert out["requires_rendering"] is True
    assert out["render_escalation"] == {}


# ── Selective escalation wiring (#18) ────────────────────────────────────────


def _rendering_config_file(tmp_path, mode, **overrides):
    path = tmp_path / "crawl.json"
    config = {"rendering": {"mode": mode, **overrides}}
    path.write_text(json.dumps(config))
    return str(path)


def test_js_mode_escalates_only_the_pattern_that_needs_it(tmp_path, monkeypatch):
    pages = [
        PageRecord(url="https://example.com/", outlinks=1, external_outlinks=0),
        PageRecord(url="https://example.com/app/1", outlinks=0, external_outlinks=0),
        PageRecord(url="https://example.com/app/2", outlinks=0, external_outlinks=0),
    ]
    links = [LinkEdge("https://example.com/", "https://example.com/app/1", "", False)]

    def fake_spider(*args, **kwargs):
        result = SpiderResult()
        result.pages = pages
        result.links = links
        result.start_page_evidence = {"html": "<html><body>hi</body></html>", "outlinks": 1}
        return result

    monkeypatch.setattr(spider_mod, "crawl_site", fake_spider)

    import seohead.tools.render as render_mod

    def fake_render_check(url, **kwargs):
        return {"ok": True, "js_dependent": "/app/" in url, "empty_shell": None}

    def fake_render_document(url, rendering_config, artifacts_dir=None):
        return {
            "ok": True,
            "html": '<html><body><a href="/app/extra">x</a></body></html>',
            "final_url": url,
        }

    monkeypatch.setattr(render_mod, "render_check", fake_render_check)
    monkeypatch.setattr(render_mod, "render_document", fake_render_document)

    config_path = _rendering_config_file(
        tmp_path, "js", escalation={"sample_per_pattern": 1, "max_render_urls": 10}
    )
    out = handlers.crawl_site(url="https://example.com/", config=config_path)

    escalation = out["render_escalation"]
    assert escalation["mode"] == "js"
    # One probe for "/" and one for the "/app/*" pattern -- never one per page.
    assert escalation["probe_requests"] == 2
    assert escalation["render_requests"] == 2  # both app/1 and app/2, not just the sample
    assert pages[1].representation == "rendered"
    assert pages[2].representation == "rendered"
    assert pages[0].representation == "static"


def test_legacy_fragment_mode_needs_no_browser(tmp_path, monkeypatch):
    start = PageRecord(url="https://example.com/", outlinks=1, external_outlinks=0)

    def fake_spider(*args, **kwargs):
        result = SpiderResult()
        result.pages = [start]
        result.start_page_evidence = {"html": "<html><body>hi</body></html>", "outlinks": 1}
        return result

    monkeypatch.setattr(spider_mod, "crawl_site", fake_spider)

    class _FakeResponse:
        def __init__(self, text):
            self.text = text

    class _FakeClient:
        def __init__(self, responses):
            self.responses = responses

        def get(self, url):
            return _FakeResponse(self.responses[url])

        def close(self):
            pass

    responses = {
        "https://example.com/": '<meta name="fragment" content="!">',
        "https://example.com/?_escaped_fragment_=": "<html><body>fully rendered</body></html>",
    }

    import seohead.recon.net as net_mod

    monkeypatch.setattr(
        net_mod, "http_client", lambda timeout, **kw: (_FakeClient(responses), True)
    )
    # No real DNS: the address guard is exercised on its own (test_render.py,
    # test_crawl_safety.py), this test is only about the legacy-fragment wiring.
    monkeypatch.setattr(net_mod, "validate_url", lambda url: url)

    config_path = _rendering_config_file(tmp_path, "legacy_fragment")
    out = handlers.crawl_site(url="https://example.com/", config=config_path)

    assert out["render_escalation"]["mode"] == "legacy_fragment"
    assert start.representation == "legacy_fragment"


def test_raw_mode_never_imports_playwright(tmp_path, monkeypatch):
    """The default mode must not touch Playwright at all -- browser rendering
    is never required for the test suite, and this proves the import path is
    not even attempted."""
    import builtins

    real_import = builtins.__import__

    def fail_on_playwright(name, *a, **kw):
        if name.startswith("playwright"):
            raise AssertionError("raw mode must never import playwright")
        return real_import(name, *a, **kw)

    fake = _fake_spider_with_start_page(2, 0, "<html><body>hi</body></html>")
    monkeypatch.setattr(spider_mod, "crawl_site", fake)
    monkeypatch.setattr(builtins, "__import__", fail_on_playwright)

    handlers.crawl_site(url="https://example.com/")
