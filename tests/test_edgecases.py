"""Regression tests for defects found in the adversarial review."""

from __future__ import annotations

import csv
import os
import shutil

from seohead.sf.config import apply_profile, load_config
from seohead.sf.core.audit import run_audit
from seohead.sf.core.context import AuditContext
from seohead.sf.core.loader import load_exports
from seohead.sf.core.normalize import to_float, to_int
from seohead.sf.reporters.md_reporter import _esc

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


# --- normalize: non-finite values must not crash or poison JSON -------------
def test_to_int_handles_non_finite():
    assert to_int("inf") is None
    assert to_int(float("inf")) is None
    assert to_int("nan") is None
    assert to_int("-inf") is None
    assert to_int("42") == 42


def test_to_float_drops_non_finite():
    assert to_float("inf") is None
    assert to_float(float("nan")) is None
    assert to_float("3.5") == 3.5


# --- context: duplicate URL rows must not desync pages/page_by_url ----------
def test_duplicate_urls_collapse(tmp_path):
    rows = [
        ["https://example.com/", "text/html", "200", "OK", "Indexable"],
        ["https://example.com/", "text/html", "200", "OK", "Indexable"],  # duplicate
        ["https://example.com/x", "text/html", "200", "OK", "Indexable"],
    ]
    p = tmp_path / "internal_all.csv"
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Address", "Content Type", "Status Code", "Status", "Indexability"])
        w.writerows(rows)
    ctx = AuditContext(load_exports(str(tmp_path)), load_config(None))
    urls = [pg.url for pg in ctx.pages]
    assert urls == ["https://example.com/", "https://example.com/x"]
    assert len(ctx.page_by_url) == len(ctx.pages)


# --- inlinks: occurrences_count = unique source pages, not link rows --------
def test_occurrences_count_is_unique_sources(tmp_path):
    shutil.copy(os.path.join(FIXTURES, "internal_all.csv"), tmp_path / "internal_all.csv")
    inl = tmp_path / "response_codes_client_error_(4xx)_inlinks.csv"
    with open(inl, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "Source",
                "Destination",
                "Anchor Text",
                "Status Code",
                "Follow",
                "Link Position",
                "Link Path",
            ]
        )
        # 3 link rows but only 2 distinct source pages
        w.writerow(
            [
                "https://example.com/",
                "https://example.com/old-page",
                "a",
                "404",
                "true",
                "Content",
                "/a",
            ]
        )
        w.writerow(
            [
                "https://example.com/",
                "https://example.com/old-page",
                "b",
                "404",
                "true",
                "Footer",
                "/b",
            ]
        )
        w.writerow(
            [
                "https://example.com/page-a",
                "https://example.com/old-page",
                "c",
                "404",
                "true",
                "Content",
                "/c",
            ]
        )
    res = run_audit(input_mode="parse-exports", exports_dir=str(tmp_path), log=lambda m: None)
    issue = next(i for i in res.issues if i.check == "BROKEN_INTERNAL_LINK")
    assert issue.occurrences_count == 2  # unique sources
    assert len(issue.locations) == 3  # but all link instances kept


# --- config: profile override wins even when config.json pins a profile -----
def test_load_config_does_not_preexpand_profile(tmp_path):
    import json

    p = tmp_path / "config.json"
    with p.open("w", encoding="utf-8") as stream:
        json.dump({"profile": "lite"}, stream)
    cfg = load_config(str(p))
    # profile recorded, but exports NOT yet collapsed to lite (so an override can win)
    assert cfg["profile"] == "lite"
    assert "Sitemaps:Orphan URLs" in cfg["exports"]["tabs"]
    # override to full -> full export set; collapse to lite -> orphan tab gone
    cfg["profile"] = "full"
    assert "Sitemaps:Orphan URLs" in apply_profile(cfg)["exports"]["tabs"]
    cfg["profile"] = "lite"
    assert "Sitemaps:Orphan URLs" not in apply_profile(cfg)["exports"]["tabs"]


# --- markdown: backslash escaped before pipe --------------------------------
def test_md_escape_backslash_then_pipe():
    assert _esc(r"foo\bar") == r"foo\\bar"
    assert _esc("a|b") == r"a\|b"
    assert _esc(r"c\|d") == r"c\\\|d"
