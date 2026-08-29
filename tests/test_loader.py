"""Loader: autodetection and encoding-safe reads."""

from __future__ import annotations

import os

import pytest

from seohead.sf.core.loader import discover_exports, load_exports, read_table


def test_discovers_internal_and_inlinks(exports_dir):
    found = discover_exports(exports_dir)
    assert "internal_all" in found
    assert "inlinks_4xx" in found
    # the inlinks file must NOT be mistaken for the 4xx response-code tab
    assert "resp_4xx" not in found


def test_reads_utf8_bom_content(exports_dir):
    df = read_table(os.path.join(exports_dir, "internal_all.csv"))
    assert "Address" in df.columns
    assert any("Industrial Pump Store" in str(v) for v in df["Title 1"].tolist())


def test_required_export_enforced(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        load_exports(str(empty))


def test_load_reports_found_and_missing(exports_dir):
    loaded = load_exports(exports_dir)
    assert "internal_all" in loaded.found
    assert loaded.has("inlinks_4xx")
    assert "sitemap_in" in loaded.missing
