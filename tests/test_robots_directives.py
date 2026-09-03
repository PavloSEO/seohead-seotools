"""Regression tests for indexability: robots directives and the document title.

Two defects with the same shape — a page's own markup says one thing and the
audit reads another. A wrong indexability verdict is a top-line error: it is
the first column of every report.
"""

from __future__ import annotations

import csv

from seohead.crawl.collect import PageRecord
from seohead.crawl.evidence import _indexability
from seohead.sf.config import load_config
from seohead.sf.core.context import AuditContext
from seohead.sf.core.loader import load_exports
from seohead.sf.core.rules import check_canonical_directives
from seohead.tools.parser import parse_html, robots_directives


# --- directive parsing ------------------------------------------------------
def test_none_is_shorthand_for_noindex_nofollow():
    # "none" contains neither substring, so a substring search misses it.
    assert {"noindex", "nofollow"} <= robots_directives("none")


def test_user_agent_prefix_is_stripped():
    # X-Robots-Tag may address one crawler: "googlebot: noindex, nofollow".
    assert "noindex" in robots_directives("googlebot: noindex, nofollow")


def test_valued_directives_keep_their_value():
    tokens = robots_directives("index, max-snippet:-1, max-image-preview:large")
    assert "max-snippet:-1" in tokens
    assert "noindex" not in tokens


def test_empty_and_none_inputs():
    assert robots_directives(None, "") == set()


# --- collection -------------------------------------------------------------
def test_crawler_addressed_tags_are_collected():
    html = (
        '<html><head><meta name="robots" content="index">'
        '<meta name="googlebot" content="noindex"></head><body>x</body></html>'
    )
    parsed = parse_html(html, "https://example.com/")
    # "robots" keeps its literal meaning; robots_meta carries every tag.
    assert parsed["robots"] == "index"
    assert parsed["robots_meta"] == ["index", "noindex"]


def test_unrelated_meta_names_are_not_directives():
    html = '<html><head><meta name="viewport" content="noindex"></head></html>'
    assert parse_html(html, "https://example.com/")["robots_meta"] == []


# --- indexability -----------------------------------------------------------
def test_indexability_honours_none_and_googlebot():
    def verdict(**kw):
        return _indexability(PageRecord(url="https://e.com/", status_code=200, **kw))[0]

    assert verdict(meta_robots="none") == "Non-Indexable"
    assert verdict(x_robots="googlebot: noindex") == "Non-Indexable"
    assert verdict(meta_robots="index, follow") == "Indexable"


def test_noindex_check_fires_on_none(tmp_path):
    path = tmp_path / "internal_all.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Address", "Content Type", "Status Code", "Indexability", "Meta Robots 1"])
        writer.writerow(["https://example.com/p", "text/html", "200", "Indexable", "none"])
    ctx = AuditContext(load_exports(str(tmp_path)), load_config(None))
    check_canonical_directives(ctx)
    assert any(issue.check == "NOINDEX" for issue in ctx.issues)


# --- document title ---------------------------------------------------------
def test_svg_title_is_not_the_page_title():
    html = (
        "<html><head><svg><title>Menu</title></svg>"
        "<title>The real one</title></head><body>x</body></html>"
    )
    assert parse_html(html, "https://example.com/")["title"] == "The real one"


def test_svg_title_does_not_hide_a_missing_title():
    html = "<html><head></head><body><svg><title>Close</title></svg></body></html>"
    assert parse_html(html, "https://example.com/")["title"] is None
