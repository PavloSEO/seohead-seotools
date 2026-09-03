"""BAD_REDIRECT_TYPE fires on the status code, which is what carries permanence."""

from __future__ import annotations

import csv

from seohead.sf.config import load_config
from seohead.sf.core.context import AuditContext
from seohead.sf.core.loader import load_exports
from seohead.sf.core.rules import check_redirect_type

ROWS = [
    # address, status, redirect type as SF writes it, redirect url
    ("https://example.com/moved-302", "302", "HTTP Redirect", "https://example.com/new"),
    ("https://example.com/moved-307", "307", "HTTP Redirect", "https://example.com/new"),
    ("https://example.com/other-303", "303", "HTTP Redirect", "https://example.com/new"),
    ("https://example.com/moved-301", "301", "HTTP Redirect", "https://example.com/new"),
    ("https://example.com/hsts", "307", "HSTS Policy", "https://example.com/x"),
    ("https://example.com/ok", "200", "", ""),
]


def _ctx(tmp_path):
    path = tmp_path / "internal_all.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "Address",
                "Content Type",
                "Status Code",
                "Indexability",
                "Redirect Type",
                "Redirect URL",
            ]
        )
        for address, status, rtype, rurl in ROWS:
            writer.writerow([address, "text/html", status, "Indexable", rtype, rurl])
    return AuditContext(load_exports(str(tmp_path)), load_config(None))


def test_temporary_redirects_are_flagged(tmp_path):
    ctx = _ctx(tmp_path)
    check_redirect_type(ctx)
    flagged = {issue.target_url for issue in ctx.issues if issue.check == "BAD_REDIRECT_TYPE"}
    assert flagged == {
        "https://example.com/moved-302",
        "https://example.com/moved-307",
        "https://example.com/other-303",
        "https://example.com/hsts",
    }


def test_permanent_and_non_redirects_are_not_flagged(tmp_path):
    ctx = _ctx(tmp_path)
    check_redirect_type(ctx)
    flagged = {issue.target_url for issue in ctx.issues}
    assert "https://example.com/moved-301" not in flagged
    assert "https://example.com/ok" not in flagged


def test_the_mechanism_column_is_reported_not_matched(tmp_path):
    # Redirect Type names the mechanism; searching it for "302"/"temporary"
    # matched nothing, which is what left this check dead.
    ctx = _ctx(tmp_path)
    check_redirect_type(ctx)
    types = {issue.details.get("redirect_type") for issue in ctx.issues}
    assert types == {"HTTP Redirect", "HSTS Policy"}
