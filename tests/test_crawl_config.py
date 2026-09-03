"""Configuration resolution, validation, and the run manifest.

The manifest is the point: two thirds of these settings change what an audit
finds, so a report that does not record them is not comparable to any other.
"""

import json

import pytest

from seohead.crawl import config as cfg


def test_defaults_load_and_validate():
    resolved = cfg.load()
    assert resolved["limits"]["max_urls"] == cfg.DEFAULTS["limits"]["max_urls"]
    assert resolved["robots"]["policy"] == "respect"


def test_every_setting_is_classified_as_results_affecting_or_not():
    """A new setting cannot be added without deciding whether it changes findings.

    Silence here is how a report stops being reproducible: a setting that moves
    the results but is absent from the manifest makes two audits differ for no
    recorded reason.
    """
    cost_only = {
        "http.timeout_seconds",  # also results-affecting; listed below
        "limits.max_response_bytes",
        "output.dir",
        "output.write_pages_jsonl",
        "speed.max_delay_seconds",
    }
    every = set(cfg._flatten(cfg.DEFAULTS))
    unclassified = every - cfg.RESULTS_AFFECTING - cost_only
    assert not unclassified, f"unclassified settings: {sorted(unclassified)}"


def test_results_affecting_names_only_real_settings():
    every = set(cfg._flatten(cfg.DEFAULTS))
    assert cfg.RESULTS_AFFECTING <= every, sorted(cfg.RESULTS_AFFECTING - every)


def test_store_and_crawl_are_independent_for_every_link_type():
    """Two different questions: keep it in the report, versus request it."""
    for link_type, pair in cfg.DEFAULTS["discovery"].items():
        if isinstance(pair, dict):
            assert set(pair) == {"store", "crawl"}, link_type


# ── precedence ──────────────────────────────────────────────────────────────


def test_file_overrides_defaults(tmp_path):
    path = tmp_path / "crawl.json"
    path.write_text(json.dumps({"limits": {"max_urls": 42}}))
    assert cfg.load(str(path))["limits"]["max_urls"] == 42


def test_environment_overrides_the_file(tmp_path, monkeypatch):
    path = tmp_path / "crawl.json"
    path.write_text(json.dumps({"limits": {"max_urls": 42}}))
    monkeypatch.setenv("SEOHEAD_CRAWL_MAX_URLS", "7")
    assert cfg.load(str(path))["limits"]["max_urls"] == 7


def test_explicit_arguments_override_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("SEOHEAD_CRAWL_MAX_URLS", "7")
    resolved = cfg.load(overrides={"limits.max_urls": 3})
    assert resolved["limits"]["max_urls"] == 3


def test_an_unset_override_does_not_erase_a_configured_value(tmp_path):
    path = tmp_path / "crawl.json"
    path.write_text(json.dumps({"limits": {"max_urls": 42}}))
    resolved = cfg.load(str(path), overrides={"limits.max_urls": None})
    assert resolved["limits"]["max_urls"] == 42


def test_environment_values_take_the_type_of_the_default(monkeypatch):
    monkeypatch.setenv("SEOHEAD_CRAWL_MIN_DELAY", "1.5")
    monkeypatch.setenv("SEOHEAD_CRAWL_MAX_DEPTH", "2")
    resolved = cfg.load()
    assert resolved["speed"]["min_delay_seconds"] == 1.5
    assert resolved["limits"]["max_depth"] == 2


def test_a_malformed_environment_value_is_refused_by_name(monkeypatch):
    monkeypatch.setenv("SEOHEAD_CRAWL_MAX_URLS", "lots")
    with pytest.raises(cfg.ConfigError, match="SEOHEAD_CRAWL_MAX_URLS"):
        cfg.load()


# ── validation ──────────────────────────────────────────────────────────────


def test_an_unknown_setting_is_refused_with_its_path(tmp_path):
    path = tmp_path / "crawl.json"
    path.write_text(json.dumps({"scope": {"exclude_pattern": ["typo"]}}))
    with pytest.raises(cfg.ConfigError, match="scope.exclude_pattern"):
        cfg.load(str(path))


def test_free_form_headers_are_a_leaf_not_a_branch(tmp_path):
    """Arbitrary header names must not be mistaken for unknown settings."""
    path = tmp_path / "crawl.json"
    path.write_text(json.dumps({"http": {"headers": {"Accept-Language": "de"}}}))
    assert cfg.load(str(path))["http"]["headers"]["Accept-Language"] == "de"


@pytest.mark.parametrize(
    "override,message",
    [
        ({"robots.policy": "maybe"}, "robots.policy"),
        ({"scope.internal": "everything"}, "scope.internal"),
        ({"limits.max_urls": 0}, "max_urls"),
        ({"limits.max_depth": -1}, "max_depth"),
        ({"speed.min_delay_seconds": -1}, "min_delay_seconds"),
    ],
)
def test_invalid_values_are_refused(override, message):
    with pytest.raises(cfg.ConfigError, match=message):
        cfg.load(overrides=override)


def test_a_missing_file_is_refused_rather_than_ignored():
    with pytest.raises(cfg.ConfigError, match="cannot read config"):
        cfg.load("/nonexistent/crawl.json")


def test_malformed_json_is_refused_by_name(tmp_path):
    path = tmp_path / "crawl.json"
    path.write_text("{not json")
    with pytest.raises(cfg.ConfigError, match="not valid JSON"):
        cfg.load(str(path))


# ── manifest ────────────────────────────────────────────────────────────────


def test_the_manifest_records_resolved_values_not_their_source():
    manifest = cfg.manifest(cfg.load(overrides={"limits.max_urls": 11}))
    assert manifest["limits.max_urls"] == 11


def test_two_runs_differing_in_a_results_affecting_setting_differ_in_the_manifest():
    first = cfg.manifest(cfg.load(overrides={"robots.policy": "respect"}))
    second = cfg.manifest(cfg.load(overrides={"robots.policy": "report_only"}))
    assert first != second
    assert [k for k in first if first[k] != second[k]] == ["robots.policy"]


def test_a_cost_only_setting_does_not_change_the_manifest():
    first = cfg.manifest(cfg.load(overrides={"output.dir": "/tmp/a"}))
    second = cfg.manifest(cfg.load(overrides={"output.dir": "/tmp/b"}))
    assert first == second


def test_the_manifest_is_json_serialisable():
    json.dumps(cfg.manifest(cfg.load()))


# ── politeness ──────────────────────────────────────────────────────────────


def test_the_effective_rate_is_derived_from_the_combination_not_one_knob():
    assert cfg.effective_request_rate(cfg.load(overrides={"speed.min_delay_seconds": 0.5})) == 2.0
    assert cfg.effective_request_rate(cfg.load(overrides={"speed.min_delay_seconds": 2.0})) == 0.5


def test_no_delay_reports_an_unbounded_rate():
    rate = cfg.effective_request_rate(cfg.load(overrides={"speed.min_delay_seconds": 0}))
    assert rate == float("inf")
