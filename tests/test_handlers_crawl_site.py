"""The handler layer wires the crawl config into the collector and back into
the audit — this is where a checkpoint path, a duration budget, and a finish
reason actually reach the crawler and the report. No network: the crawler
itself is replaced with a fake."""

import json

import seohead.crawl.spider as spider_mod
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


def test_link_position_classify_defaults_off_and_is_not_computed(monkeypatch):
    captured = {}

    def fake(*args, **kwargs):
        captured.update(kwargs)
        result = SpiderResult()
        result.links = [LinkEdge("https://example.com/", "https://example.com/a", "", False, "nav")]
        return result

    monkeypatch.setattr(spider_mod, "crawl_site", fake)
    out = handlers.crawl_site(url="https://example.com/")
    assert captured["classify_links"] is False
    assert out["link_position"] == {}


def test_link_position_classify_config_reaches_the_spider_and_the_output(tmp_path, monkeypatch):
    """Issue #20 part 3: link position classification, wired end to end
    through the handler that meets the collector and the audit."""
    config = tmp_path / "crawl.json"
    config.write_text(json.dumps({"link_position": {"classify": True}}))

    def fake(*args, **kwargs):
        captured.update(kwargs)
        result = SpiderResult()
        result.links = [
            LinkEdge("https://example.com/", "https://example.com/orphan", "", False, "nav"),
            LinkEdge("https://example.com/x", "https://example.com/orphan", "", False, "footer"),
            LinkEdge(
                "https://example.com/blog", "https://example.com/linked", "", False, "content"
            ),
        ]
        return result

    captured = {}
    monkeypatch.setattr(spider_mod, "crawl_site", fake)

    out = handlers.crawl_site(url="https://example.com/", config=str(config))

    assert captured["classify_links"] is True
    boilerplate_only = out["link_position"]["pages_boilerplate_only"]
    assert boilerplate_only == ["https://example.com/orphan"]
    # The same fact also reaches the audit as a registered finding.
    assert out["summary"]["by_check"].get("INLINK_BOILERPLATE_ONLY") == 1
