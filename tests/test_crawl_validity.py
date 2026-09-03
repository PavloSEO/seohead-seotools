"""A crawl that proved nothing must not report a perfect score.

health_score is the number an operator reads first and the number that reaches a
client report. Rendering "no data" as "no problems" is the one place the toolkit
used to lie about what it had not measured.
"""

import csv

from seohead.sf.config import load_config
from seohead.sf.core.aggregate import aggregate
from seohead.sf.core.context import AuditContext
from seohead.sf.core.loader import load_exports
from seohead.sf.reporters.md_reporter import write_markdown
from seohead.sf.tasks import build_tasks, render_tasks_md

HEADER = ["Address", "Content Type", "Status Code", "Status", "Indexability"]


def _ctx(tmp_path, rows):
    path = tmp_path / "internal_all.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(HEADER)
        writer.writerows(rows)
    return AuditContext(load_exports(str(tmp_path)), load_config(None))


def _run() -> dict:
    return {"input_mode": "crawl", "generated_at": "2026-09-03T00:00:00Z", "project": "example"}


def test_no_response_start_url_scores_null_not_100(tmp_path):
    ctx = _ctx(tmp_path, [["https://example.com/", "", "0", "No Response", "Non-Indexable"]])
    result = aggregate(ctx, _run(), {}, {})
    assert result.summary["health_score"] is None
    assert result.summary["health_score_reason"]
    assert result.run["crawl_valid"] is False


def test_empty_crawl_scores_null(tmp_path):
    ctx = _ctx(tmp_path, [])
    result = aggregate(ctx, _run(), {}, {})
    assert result.summary["health_score"] is None
    assert result.run["crawl_valid"] is False
    assert "no URLs" in result.run["crawl_invalid_reason"]


def test_a_normal_crawl_still_scores_and_stays_valid(tmp_path):
    ctx = _ctx(
        tmp_path,
        [
            ["https://example.com/", "text/html", "200", "OK", "Indexable"],
            ["https://example.com/x", "text/html", "200", "OK", "Indexable"],
        ],
    )
    result = aggregate(ctx, _run(), {}, {})
    assert isinstance(result.summary["health_score"], int)
    assert result.run["crawl_valid"] is True
    assert "health_score_reason" not in result.summary


def test_a_crawl_far_below_the_sitemap_is_partial_but_still_scored(tmp_path):
    """A deliberate sample is a supported mode, so it is labelled, not voided."""
    ctx = _ctx(tmp_path, [["https://example.com/", "text/html", "200", "OK", "Indexable"]])
    result = aggregate(ctx, _run(), {}, {"urls_in_sitemap": 1000})
    assert result.run["crawl_partial"] is True
    assert isinstance(result.summary["health_score"], int)
    assert "1 of 1000" in result.summary["health_score_scope"]


def test_a_full_crawl_is_not_marked_partial(tmp_path):
    ctx = _ctx(
        tmp_path,
        [
            ["https://example.com/", "text/html", "200", "OK", "Indexable"],
            ["https://example.com/x", "text/html", "200", "OK", "Indexable"],
        ],
    )
    result = aggregate(ctx, _run(), {}, {"urls_in_sitemap": 2})
    assert result.run["crawl_partial"] is False
    assert "health_score_scope" not in result.summary


def test_markdown_leads_with_the_failure_not_a_score(tmp_path):
    ctx = _ctx(tmp_path, [["https://example.com/", "", "0", "No Response", "Non-Indexable"]])
    out = tmp_path / "audit.md"
    write_markdown(aggregate(ctx, _run(), {}, {}), str(out))
    md = out.read_text(encoding="utf-8")
    assert "Crawl failed" in md
    assert "Health score: None" not in md


def test_tasks_report_leads_with_the_failure(tmp_path):
    ctx = _ctx(tmp_path, [["https://example.com/", "", "0", "No Response", "Non-Indexable"]])
    audit = aggregate(ctx, _run(), {}, {}).to_json()
    text = render_tasks_md(build_tasks(audit, load_config(None)))
    assert "Crawl failed" in text
    assert "health n/a" in text
