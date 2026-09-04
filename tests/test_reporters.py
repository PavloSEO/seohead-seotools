"""Reporters: JSON validates against the schema; Markdown preserves localization."""

from __future__ import annotations

import json

from seohead.sf.reporters import write_json, write_markdown
from seohead.sf.reporters.jsonfile import validate


def test_json_validates_against_schema(result):
    assert validate(result) == []


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
