"""Inlinks localization: the broken-link DOM detail that drives the report."""

from __future__ import annotations

import csv
import os
import shutil

from seohead.sf.core.audit import run_audit
from tests.conftest import issues_of

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def test_broken_internal_link_localized(result):
    issues = issues_of(result, "BROKEN_INTERNAL_LINK")
    assert len(issues) == 1
    issue = issues[0]
    assert issue.target_url == "https://example.com/old-page"
    assert issue.status_code == 404
    assert issue.occurrences_count == 2
    assert issue.severity == "critical"

    sources = {loc["source_url"] for loc in issue.locations}
    assert sources == {"https://example.com/", "https://example.com/page-a"}

    positions = {loc["link_position"] for loc in issue.locations}
    assert positions == {"Content", "Footer"}

    paths = {loc["link_path"] for loc in issue.locations}
    assert "/html/body/main/article/p[3]/a" in paths
    # anchor + follow are captured
    by_source = {loc["source_url"]: loc for loc in issue.locations}
    assert by_source["https://example.com/"]["anchor"] == "Old page"
    assert by_source["https://example.com/"]["follow"] is True


def test_position_breakdown_in_details(result):
    issue = issues_of(result, "BROKEN_INTERNAL_LINK")[0]
    breakdown = issue.details["link_position_breakdown"]
    assert breakdown == {"Content": 1, "Footer": 1}


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
