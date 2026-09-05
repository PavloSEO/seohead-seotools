"""Reporters: JSON validates against the schema; Markdown preserves localization."""

from __future__ import annotations

import json

import pytest

from seohead.sf.config import ConfigError
from seohead.sf.core.audit import run_audit
from seohead.sf.reporters import write_json, write_markdown
from seohead.sf.reporters.jsonfile import validate
from seohead.sf.reporters.md import _esc


def test_json_validates_against_schema(result):
    assert validate(result) == []


def test_invalid_severity_override_is_rejected_before_audit_json_is_emitted(internal_only_dir):
    """Issue #211: an out-of-enum severity must never reach a check result.

    Left unchecked, TITLE_MISSING at "urgent" both dropped its issue out of
    by_severity/the weighted penalty (inflating the health score) and made
    the emitted document fail its own bundled schema.
    """
    with pytest.raises(ConfigError, match="TITLE_MISSING"):
        run_audit(
            input_mode="parse-exports",
            exports_dir=internal_only_dir,
            config_overrides={"severity_overrides": {"TITLE_MISSING": "urgent"}},
            log=lambda _: None,
        )


def test_valid_severity_override_still_produces_a_schema_valid_report(internal_only_dir):
    res = run_audit(
        input_mode="parse-exports",
        exports_dir=internal_only_dir,
        config_overrides={"severity_overrides": {"TITLE_MISSING": "notice"}},
        log=lambda _: None,
    )
    assert validate(res) == []


def test_json_roundtrip_utf8(result, tmp_path):
    path = write_json(result, str(tmp_path / "audit.json"))
    with open(path, encoding="utf-8") as stream:
        data = json.load(stream)
    assert data["schema_version"] == "2.0"
    assert data["summary"]["by_severity"]["critical"] >= 1
    # Text from the crawl export must survive the JSON round trip unchanged.
    with open(path, encoding="utf-8") as stream:
        raw = stream.read()
    assert "Page A — Shop Pumps Online" in raw


def test_ids_are_deterministic(result):
    ids = [i.id for i in result.issues]
    assert ids == sorted(ids)  # ISSUE-000001.. assigned in sorted order
    assert all(i.fingerprint for i in result.issues)


def test_markdown_has_broken_link_table(result, tmp_path):
    path = write_markdown(result, str(tmp_path / "audit.md"))
    with open(path, encoding="utf-8") as stream:
        text = stream.read()
    assert "BROKEN_INTERNAL_LINK" in text
    assert "/html/body/footer/nav/a[2]" in text  # XPath location details are rendered.
    assert "Sitemap & robots" not in text or "Health score" in text


def test_markdown_h1_multiple_texts(result, tmp_path):
    path = write_markdown(result, str(tmp_path / "audit.md"))
    with open(path, encoding="utf-8") as stream:
        text = stream.read()
    assert "Second H1 Heading" in text


def test_md_escape_backslash_then_pipe():
    assert _esc(r"foo\bar") == r"foo\\bar"
    assert _esc("a|b") == r"a\|b"
    assert _esc(r"c\|d") == r"c\\\|d"
