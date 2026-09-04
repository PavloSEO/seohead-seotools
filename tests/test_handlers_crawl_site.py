"""The handler layer wires the crawl config into the collector and back into
the audit — this is where a checkpoint path, a duration budget, and a finish
reason actually reach the crawler and the report. No network: the crawler
itself is replaced with a fake."""

import seohead.crawl.spider as spider_mod
from seohead.crawl.spider import SpiderResult
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
