"""Inlinks localization: the broken-link DOM detail that drives the report."""

from __future__ import annotations

from tests.conftest import issues_of


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
