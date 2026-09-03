"""URL_REPETITIVE_PATH is about a repeated word, not a repeated number.

A path segment that repeats usually means a duplicated prefix or a crawl trap.
A number that repeats usually means a date or a pair of ids, and flagging those
puts the finding on every dated post a site has ever published.
"""

from __future__ import annotations

import csv

import pytest

from seohead.sf.config import load_config
from seohead.sf.core.context import AuditContext
from seohead.sf.core.loader import load_exports
from seohead.sf.core.rules import check_url_extra

REPEATED_WORD = [
    "https://example.com/shop/shop/item/",
    "https://example.com/en/products/en/",
    "https://example.com/blog/category/blog/",
]

REPEATED_NUMBER = [
    "https://example.com/2024/01/01/my-post/",  # default WordPress permalink
    "https://example.com/catalog/12/12/",
    "https://example.com/2011/11/11/",
]

CLEAN = [
    "https://example.com/catalogue/chairs/oak/",
    "https://example.com/blog/2024/05/2024-review/",
]


def _flagged(tmp_path, url) -> bool:
    path = tmp_path / "internal_all.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Address", "Content Type", "Status Code", "Indexability"])
        writer.writerow([url, "text/html", "200", "Indexable"])
    ctx = AuditContext(load_exports(str(tmp_path)), load_config(None))
    check_url_extra(ctx)
    return any(issue.check == "URL_REPETITIVE_PATH" for issue in ctx.issues)


@pytest.mark.parametrize("url", REPEATED_WORD)
def test_repeated_word_is_flagged(tmp_path, url):
    assert _flagged(tmp_path, url)


@pytest.mark.parametrize("url", REPEATED_NUMBER)
def test_repeated_number_is_not_flagged(tmp_path, url):
    assert not _flagged(tmp_path, url)


@pytest.mark.parametrize("url", CLEAN)
def test_distinct_segments_are_not_flagged(tmp_path, url):
    assert not _flagged(tmp_path, url)
