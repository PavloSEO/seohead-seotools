"""Outlinks counts internal links; External Outlinks is a separate count.

The two columns are disjoint, not whole-and-part. Treating the second as a
subset of the first reports "no internal links" for any page that links out
more than it links in — a normal shape for an article with citations.
"""

from __future__ import annotations

import csv

from seohead.crawl.collect import PageRecord
from seohead.crawl.evidence import _row
from seohead.sf.config import load_config
from seohead.sf.core.context import AuditContext
from seohead.sf.core.loader import load_exports
from seohead.sf.core.rules import check_links_extra

COLUMNS = [
    "Address",
    "Content Type",
    "Status Code",
    "Indexability",
    "Outlinks",
    "External Outlinks",
]


def _flagged(tmp_path, rows) -> set[str]:
    path = tmp_path / "internal_all.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for address, outlinks, external in rows:
            writer.writerow([address, "text/html", "200", "Indexable", outlinks, external])
    ctx = AuditContext(load_exports(str(tmp_path)), load_config(None))
    check_links_extra(ctx)
    return {issue.target_url for issue in ctx.issues if issue.check == "NO_INTERNAL_OUTLINKS"}


def test_more_external_than_internal_is_not_a_dead_end(tmp_path):
    flagged = _flagged(tmp_path, [("https://example.com/cited", 10, 15)])
    assert flagged == set()


def test_a_page_with_no_internal_links_is_still_flagged(tmp_path):
    flagged = _flagged(tmp_path, [("https://example.com/dead-end", 0, 15)])
    assert flagged == {"https://example.com/dead-end"}


def test_the_projection_reports_internal_links_in_that_column(tmp_path):
    # The collector counts every link it found; the column counts internal ones.
    record = PageRecord(
        url="https://example.com/", status_code=200, outlinks=25, external_outlinks=15
    )
    row = _row(record)
    assert row["Outlinks"] == 10
    assert row["External Outlinks"] == 15


def test_the_projection_never_reports_a_negative_count():
    record = PageRecord(
        url="https://example.com/", status_code=200, outlinks=3, external_outlinks=5
    )
    assert _row(record)["Outlinks"] == 0
