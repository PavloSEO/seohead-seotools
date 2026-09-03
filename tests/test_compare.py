"""Crawl-to-crawl comparison: fixed vs merely-not-recrawled must not look alike.

The distinction between "left" and "disappeared" is the entire value of this
module. A naive diff of two finding sets cannot make it; this one can because
it also looks at which URLs were actually crawled each time.
"""

import pytest

from seohead.sf.core.compare import CompareError, compare, preflight


def _audit(urls, issues, **run):
    return {
        "run": {"generated_at": "t", **run},
        "pages": [{"url": u} for u in urls],
        "issues": [{"check": c, "target_url": u} for c, u in issues],
    }


def test_a_fixed_page_lands_in_left_not_disappeared():
    """Still crawled, no longer matching — a real fix."""
    before = _audit(["https://e.com/a"], [("BROKEN", "https://e.com/a")])
    after = _audit(["https://e.com/a"], [])
    result = compare(before, after)
    assert [i["target_url"] for i in result["left"]] == ["https://e.com/a"]
    assert result["disappeared"] == []


def test_an_uncrawled_page_lands_in_disappeared_not_left():
    """Not in this crawl at all — the fix is unproven, not achieved."""
    before = _audit(["https://e.com/a"], [("BROKEN", "https://e.com/a")])
    after = _audit(["https://e.com/b"], [])  # a was never re-crawled
    result = compare(before, after)
    assert result["left"] == []
    assert [i["target_url"] for i in result["disappeared"]] == ["https://e.com/a"]


def test_a_genuinely_new_page_with_a_finding_is_appeared_not_entered():
    before = _audit(["https://e.com/a"], [])
    after = _audit(["https://e.com/a", "https://e.com/new"], [("BROKEN", "https://e.com/new")])
    result = compare(before, after)
    assert [i["target_url"] for i in result["appeared"]] == ["https://e.com/new"]
    assert result["entered"] == []


def test_a_new_finding_on_a_previously_crawled_page_is_entered():
    before = _audit(["https://e.com/a"], [])
    after = _audit(["https://e.com/a"], [("BROKEN", "https://e.com/a")])
    result = compare(before, after)
    assert [i["target_url"] for i in result["entered"]] == ["https://e.com/a"]
    assert result["appeared"] == []


def test_an_unchanged_finding_appears_in_no_bucket():
    before = _audit(["https://e.com/a"], [("BROKEN", "https://e.com/a")])
    after = _audit(["https://e.com/a"], [("BROKEN", "https://e.com/a")])
    result = compare(before, after)
    assert result["summary"] == {
        "entered": 0,
        "left": 0,
        "appeared": 0,
        "disappeared": 0,
        "by_check": {},
    }


def test_the_four_sets_are_disjoint_and_exhaustive():
    before = _audit(
        ["https://e.com/a", "https://e.com/b", "https://e.com/c"],
        [("X", "https://e.com/a"), ("X", "https://e.com/b")],
    )
    after = _audit(
        ["https://e.com/a", "https://e.com/c", "https://e.com/d"],
        [("X", "https://e.com/c"), ("X", "https://e.com/d")],
    )
    result = compare(before, after)
    all_urls = [
        i["target_url"]
        for bucket in ("entered", "left", "appeared", "disappeared")
        for i in result[bucket]
    ]
    assert sorted(all_urls) == [
        "https://e.com/a",
        "https://e.com/b",
        "https://e.com/c",
        "https://e.com/d",
    ]
    assert len(all_urls) == len(set(all_urls))  # disjoint


def test_by_check_summary_matches_the_bucket_contents():
    before = _audit(["https://e.com/a"], [("BROKEN", "https://e.com/a")])
    after = _audit(["https://e.com/a"], [])
    result = compare(before, after)
    assert result["summary"]["by_check"]["BROKEN"]["left"] == 1


def test_output_is_deterministic_regardless_of_input_dict_order():
    before = _audit(["https://e.com/b", "https://e.com/a"], [("X", "https://e.com/b")])
    after = _audit(["https://e.com/a", "https://e.com/b"], [("X", "https://e.com/a")])
    r1 = compare(before, after)
    r2 = compare(before, after)
    assert r1["entered"] == r2["entered"]
    assert [i["target_url"] for i in r1["entered"]] == ["https://e.com/a"]


# ── preflight warnings ────────────────────────────────────────────────────


def test_a_partial_before_crawl_warns_about_disappeared_findings():
    before = _audit(["https://e.com/a"], [("X", "https://e.com/a")], crawl_partial=True)
    after = _audit([], [])
    warnings = preflight(before, after)
    assert any("disappeared" in w and "before" in w for w in warnings)


def test_an_invalid_crawl_warns_plainly():
    before = _audit([], [], crawl_valid=False)
    after = _audit(["https://e.com/a"], [])
    warnings = preflight(before, after)
    assert any("before" in w and "invalid" in w for w in warnings)


def test_differing_results_affecting_config_is_flagged_by_name():
    before = _audit(["https://e.com/a"], [], crawl_config={"robots.policy": "respect"})
    after = _audit(["https://e.com/a"], [], crawl_config={"robots.policy": "ignore"})
    warnings = preflight(before, after)
    assert any("robots.policy" in w for w in warnings)


def test_identical_config_produces_no_config_warning():
    cfg = {"robots.policy": "respect", "limits.max_urls": 200}
    before = _audit(["https://e.com/a"], [], crawl_config=cfg)
    after = _audit(["https://e.com/a"], [], crawl_config=dict(cfg))
    assert preflight(before, after) == []


def test_no_config_present_on_either_side_does_not_warn():
    before = _audit(["https://e.com/a"], [])
    after = _audit(["https://e.com/a"], [])
    assert preflight(before, after) == []


def test_warnings_are_included_in_the_compare_result():
    before = _audit([], [], crawl_valid=False)
    after = _audit(["https://e.com/a"], [])
    result = compare(before, after)
    assert result["warnings"]


# ── refusal ─────────────────────────────────────────────────────────────


def test_a_document_missing_pages_is_refused_by_name():
    before = {"run": {}, "issues": []}
    after = _audit(["https://e.com/a"], [])
    with pytest.raises(CompareError, match="before"):
        compare(before, after)


def test_a_document_missing_issues_is_refused_by_name():
    before = _audit(["https://e.com/a"], [])
    after = {"run": {}, "pages": []}
    with pytest.raises(CompareError, match="after"):
        compare(before, after)
