"""HREFLANG_MISSING_RETURN_LINK: A names B, but B never names A back.

Reciprocity is a property of the pair -- B's return annotation is only
knowable once B itself has been crawled -- so this is one of issue #15's
post-crawl passes (item 6). The existing HREFLANG_NOT_CANONICAL check already
covers a return link that points at a non-canonical version of the source, so
this file only exercises the net-new reciprocity gap.
"""

from __future__ import annotations

import csv

from seohead.sf.core.audit import run_audit

INTERNAL_COLS = ["Address", "Content Type", "Status Code", "Status", "Indexability"]
HREFLANG_COLS = ["Source", "Destination", "Hreflang"]


def _write(tmp_path, internal_rows, hreflang_rows):
    d = tmp_path / "exports"
    d.mkdir()
    with open(d / "internal_all.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(INTERNAL_COLS)
        w.writerows(internal_rows)
    with open(d / "all_hreflang.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(HREFLANG_COLS)
        w.writerows(hreflang_rows)
    return str(d)


def _fired(res, check):
    return {i.target_url: i for i in res.issues if i.check == check}


def test_a_one_way_annotation_flags_the_page_that_never_returns_it(tmp_path):
    rows = [
        ["https://example.com/en", "text/html", "200", "OK", "Indexable"],
        ["https://example.com/fr", "text/html", "200", "OK", "Indexable"],
    ]
    hreflang_rows = [["https://example.com/en", "https://example.com/fr", "fr"]]
    exports_dir = _write(tmp_path, rows, hreflang_rows)
    res = run_audit(input_mode="parse-exports", exports_dir=exports_dir, log=lambda m: None)
    fired = _fired(res, "HREFLANG_MISSING_RETURN_LINK")
    assert set(fired) == {"https://example.com/fr"}
    assert fired["https://example.com/fr"].details["expected_return_to"] == [
        "https://example.com/en"
    ]


def test_a_reciprocated_pair_does_not_fire(tmp_path):
    rows = [
        ["https://example.com/en", "text/html", "200", "OK", "Indexable"],
        ["https://example.com/fr", "text/html", "200", "OK", "Indexable"],
    ]
    hreflang_rows = [
        ["https://example.com/en", "https://example.com/fr", "fr"],
        ["https://example.com/fr", "https://example.com/en", "en"],
    ]
    exports_dir = _write(tmp_path, rows, hreflang_rows)
    res = run_audit(input_mode="parse-exports", exports_dir=exports_dir, log=lambda m: None)
    assert _fired(res, "HREFLANG_MISSING_RETURN_LINK") == {}


def test_a_target_outside_the_crawl_is_not_faulted(tmp_path):
    rows = [["https://example.com/en", "text/html", "200", "OK", "Indexable"]]
    hreflang_rows = [["https://example.com/en", "https://example.com/de", "de"]]
    exports_dir = _write(tmp_path, rows, hreflang_rows)
    res = run_audit(input_mode="parse-exports", exports_dir=exports_dir, log=lambda m: None)
    assert _fired(res, "HREFLANG_MISSING_RETURN_LINK") == {}


def test_a_one_way_pair_that_differs_only_by_path_case_still_fires(tmp_path):
    """#202: norm_url must not fold /en and /EN into one node and hide the missing return."""
    rows = [
        ["https://example.test/en", "text/html", "200", "OK", "Indexable"],
        ["https://example.test/EN", "text/html", "200", "OK", "Indexable"],
    ]
    hreflang_rows = [["https://example.test/en", "https://example.test/EN", "en"]]
    exports_dir = _write(tmp_path, rows, hreflang_rows)
    res = run_audit(input_mode="parse-exports", exports_dir=exports_dir, log=lambda m: None)
    fired = _fired(res, "HREFLANG_MISSING_RETURN_LINK")
    assert set(fired) == {"https://example.test/EN"}


def test_skips_without_the_all_hreflang_export(tmp_path):
    d = tmp_path / "exports"
    d.mkdir()
    with open(d / "internal_all.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(INTERNAL_COLS)
        w.writerow(["https://example.com/", "text/html", "200", "OK", "Indexable"])
    res = run_audit(input_mode="parse-exports", exports_dir=str(d), log=lambda m: None)
    reasons = {s.id: s.reason for s in res.skipped}
    assert "all_hreflang" in reasons["HREFLANG_MISSING_RETURN_LINK"]
