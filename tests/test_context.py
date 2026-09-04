"""Context: duplicate URL rows must not desync pages/page_by_url."""

from __future__ import annotations

import csv

from seohead.sf.config import load_config
from seohead.sf.core.context import AuditContext
from seohead.sf.core.loader import load_exports


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


def test_html_pages_excludes_redirect_and_error_stubs(tmp_path):
    """Issue #133: a 301 or 404 stub is routinely served as ``text/html`` too, so
    ``Page.is_html`` alone let both into ``html_pages()`` — the population
    ``.claude/skills/control/reference/populations.md`` defines as "fetched, 2xx, HTML by its
    own Content-Type". Only the 200 belongs in it.
    """
    rows = [
        ["https://example.com/live", "text/html", "200", "OK", "Indexable"],
        ["https://example.com/old-page", "text/html", "301", "Moved", "Non-Indexable"],
        [
            "https://example.com/gone",
            "text/html; charset=UTF-8",
            "404",
            "Not Found",
            "Non-Indexable",
        ],
    ]
    p = tmp_path / "internal_all.csv"
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Address", "Content Type", "Status Code", "Status", "Indexability"])
        w.writerows(rows)
    ctx = AuditContext(load_exports(str(tmp_path)), load_config(None))
    assert [pg.url for pg in ctx.html_pages()] == ["https://example.com/live"]
