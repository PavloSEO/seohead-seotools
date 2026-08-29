"""Rule engine: the SF-derived checks fire on the right rows."""

from __future__ import annotations

from tests.conftest import checks_in, issues_of


def test_broken_4xx(result):
    issues = issues_of(result, "BROKEN_PAGE_4XX")
    assert len(issues) == 1
    assert issues[0].target_url == "https://example.com/old-page"
    assert issues[0].status_code == 404
    assert issues[0].severity == "critical"


def test_title_missing_and_desc_missing(result):
    assert {i.target_url for i in issues_of(result, "TITLE_MISSING")} == {
        "https://example.com/no-title"
    }
    assert "https://example.com/no-title" in {
        i.target_url for i in issues_of(result, "DESC_MISSING")
    }


def test_h1_multiple_captures_texts(result):
    issues = issues_of(result, "H1_MULTIPLE")
    assert len(issues) == 1
    assert issues[0].target_url == "https://example.com/page-a"
    assert issues[0].details["h1_texts"] == ["Pump Page A", "Second H1 Heading"]


def test_title_duplicate_groups(result):
    issues = issues_of(result, "TITLE_DUPLICATE")
    urls = {i.target_url for i in issues}
    assert urls == {"https://example.com/page-a", "https://example.com/page-b"}
    # both reference the same group
    gids = {i.group_id for i in issues}
    assert len(gids) == 1
    group = next(g for g in result.groups if g.group_id in gids)
    assert group.count == 2


def test_thin_content_and_low_ratio(result):
    assert "https://example.com/page-b" in {i.target_url for i in issues_of(result, "THIN_CONTENT")}
    assert "https://example.com/page-b" in {
        i.target_url for i in issues_of(result, "LOW_TEXT_RATIO")
    }


def test_canonical_missing(result):
    assert "https://example.com/no-title" in {
        i.target_url for i in issues_of(result, "CANONICAL_MISSING")
    }


def test_slow_response(result):
    assert "https://example.com/no-title" in {
        i.target_url for i in issues_of(result, "SLOW_RESPONSE")
    }


def test_image_excluded_from_onpage(result):
    # the .jpg row must not produce title/h1/canonical on-page issues
    for check in ("TITLE_MISSING", "H1_MISSING", "CANONICAL_MISSING"):
        assert "https://example.com/image.jpg" not in {
            i.target_url for i in issues_of(result, check)
        }


def test_skipped_recorded_when_source_absent(internal_only_dir):
    from seohead.sf.core.audit import run_audit

    res = run_audit(input_mode="parse-exports", exports_dir=internal_only_dir, log=lambda m: None)
    skipped = {s.id for s in res.skipped}
    assert "BROKEN_INTERNAL_LINK" in skipped  # no inlinks export here
    assert "BROKEN_INTERNAL_LINK" not in checks_in(res)
