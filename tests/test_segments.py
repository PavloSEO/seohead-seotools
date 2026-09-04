"""Segment declaration and assignment. Pure, no network."""

import pytest

from seohead.sf.core.segments import SegmentError, assign_segments, resolve_order, segment_report

BLOG = {
    "name": "blog",
    "rules": [{"op": "prefix", "field": "url", "value": "https://example.com/blog"}],
}
CATALOGUE = {
    "name": "catalogue",
    "rules": [{"op": "prefix", "field": "url", "value": "https://example.com/shop"}],
}


def _pages(*urls):
    return [{"url": u} for u in urls]


def test_membership_is_non_exclusive_a_page_may_match_several_segments():
    tagged = {
        "name": "tagged",
        "rules": [{"op": "contains", "field": "url", "value": "/blog/"}],
    }
    pages = _pages("https://example.com/blog/post-1")
    result = assign_segments(pages, [BLOG, tagged])
    assert sorted(result["memberships"]["https://example.com/blog/post-1"]) == ["blog", "tagged"]


def test_a_page_matching_nothing_has_an_empty_membership_and_no_primary():
    pages = _pages("https://example.com/other")
    result = assign_segments(pages, [BLOG, CATALOGUE])
    assert result["memberships"]["https://example.com/other"] == []
    assert result["primary"]["https://example.com/other"] is None


def test_rules_read_post_crawl_fields_via_the_metrics_fallback():
    """A Screaming Frog Page.to_json() keeps CSV-sourced fields under
    ``metrics``; a rule targeting ``status_code`` must still see them."""
    broken = {"name": "broken", "rules": [{"op": "eq", "field": "status_code", "value": 404}]}
    pages = [
        {"url": "https://example.com/a", "metrics": {"status_code": 404}},
        {"url": "https://example.com/b", "metrics": {"status_code": 200}},
    ]
    result = assign_segments(pages, [broken])
    assert result["primary"]["https://example.com/a"] == "broken"
    assert result["primary"]["https://example.com/b"] is None


def test_a_segment_may_reference_an_earlier_segment():
    broken_blog = {
        "name": "broken-blog",
        "rules": [
            {"op": "segment", "value": "blog"},
            {"op": "prefix", "field": "url", "value": "never-matches-anything"},
        ],
    }
    pages = _pages("https://example.com/blog/post-1", "https://example.com/shop/item")
    result = assign_segments(pages, [BLOG, broken_blog])
    assert result["memberships"]["https://example.com/blog/post-1"] == ["blog", "broken-blog"]
    assert result["memberships"]["https://example.com/shop/item"] == []


def test_evaluation_order_is_deterministic_regardless_of_declaration_order():
    """Reordering the segment list must not change the resolved order or the
    resulting assignment, as long as the dependency structure is unchanged."""
    a = {"name": "a", "rules": [{"op": "prefix", "field": "url", "value": "https://example.com/a"}]}
    b = {"name": "b", "rules": [{"op": "segment", "value": "a"}]}
    c = {"name": "c", "rules": [{"op": "prefix", "field": "url", "value": "https://example.com/c"}]}

    order_1 = [seg.name for seg in resolve_order([a, b, c])]
    order_2 = [seg.name for seg in resolve_order([c, b, a])]
    order_3 = [seg.name for seg in resolve_order([b, a, c])]
    assert order_1 == order_2 == order_3

    pages = _pages("https://example.com/a/1")
    m1 = assign_segments(pages, [a, b, c])
    m2 = assign_segments(pages, [c, b, a])
    assert m1["primary"] == m2["primary"]
    assert m1["memberships"] == m2["memberships"]


def test_a_direct_cycle_is_rejected_with_the_cycle_named():
    a = {"name": "a", "rules": [{"op": "segment", "value": "b"}]}
    b = {"name": "b", "rules": [{"op": "segment", "value": "a"}]}
    with pytest.raises(SegmentError) as exc_info:
        resolve_order([a, b])
    message = str(exc_info.value)
    assert "circular segment dependency" in message
    assert "a" in message and "b" in message


def test_a_self_reference_is_rejected_as_a_cycle_of_one():
    a = {"name": "a", "rules": [{"op": "segment", "value": "a"}]}
    with pytest.raises(SegmentError, match="circular segment dependency"):
        resolve_order([a])


def test_a_reference_to_an_unknown_segment_is_rejected_by_name():
    a = {"name": "a", "rules": [{"op": "segment", "value": "does-not-exist"}]}
    with pytest.raises(SegmentError, match="unknown segment 'does-not-exist'"):
        resolve_order([a])


def test_duplicate_segment_names_are_rejected():
    with pytest.raises(SegmentError, match="duplicate segment name"):
        resolve_order([BLOG, BLOG])


def test_a_segment_with_no_rules_is_rejected_rather_than_silently_matching_nothing():
    empty = {"name": "empty", "rules": []}
    with pytest.raises(SegmentError, match="no rules"):
        resolve_order([empty])


def test_report_pages_by_segment_sums_to_the_ungrouped_total():
    pages = _pages(
        "https://example.com/blog/1",
        "https://example.com/blog/2",
        "https://example.com/shop/1",
        "https://example.com/other",
    )
    report = segment_report(pages, [], [BLOG, CATALOGUE])
    assert sum(report["pages_by_segment"].values()) == len(pages)
    assert report["pages_by_segment"]["blog"] == 2
    assert report["pages_by_segment"]["catalogue"] == 1
    assert report["pages_by_segment"]["unsegmented"] == 1


def test_report_issues_by_segment_sums_to_the_ungrouped_total():
    pages = _pages("https://example.com/blog/1", "https://example.com/shop/1")
    issues = [
        {"check": "MISSING_TITLE", "target_url": "https://example.com/blog/1"},
        {"check": "THIN_CONTENT", "target_url": "https://example.com/shop/1"},
        {"check": "ORPHAN", "target_url": "https://example.com/not-crawled"},
    ]
    report = segment_report(pages, issues, [BLOG, CATALOGUE])
    total = sum(sum(counts.values()) for counts in report["issues_by_segment"].values())
    assert total == len(issues)
    assert report["issues_by_segment"]["blog"] == {"MISSING_TITLE": 1}
    assert report["issues_by_segment"]["catalogue"] == {"THIN_CONTENT": 1}
    assert report["issues_by_segment"]["unsegmented"] == {"ORPHAN": 1}


def test_segment_definitions_accept_dataclass_instances_too():
    from seohead.sf.core.segments import Segment, SegmentRule

    seg = Segment(
        name="blog",
        rules=(SegmentRule(op="prefix", field="url", value="https://example.com/blog"),),
    )
    pages = _pages("https://example.com/blog/1")
    result = assign_segments(pages, [seg])
    assert result["primary"]["https://example.com/blog/1"] == "blog"


def test_an_unknown_rule_op_is_rejected_at_definition_time():
    bad = {"name": "bad", "rules": [{"op": "nonsense", "field": "url", "value": "x"}]}
    with pytest.raises(SegmentError, match="unknown segment rule op"):
        resolve_order([bad])
