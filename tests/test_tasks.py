"""Task backlog generation from an audit."""

from __future__ import annotations

from seohead.sf.config import load_config
from seohead.sf.reporters.jsonfile import to_dict
from seohead.sf.tasks import build_tasks, render_tasks_md


def test_groups_by_check_with_priority(result):
    backlog = build_tasks(to_dict(result), load_config(None))
    assert backlog["summary"]["tasks_total"] >= 1
    checks = {t["check"] for t in backlog["tasks"]}
    # Create one task per issue type by default.
    assert "BROKEN_INTERNAL_LINK" in checks
    bl = next(t for t in backlog["tasks"] if t["check"] == "BROKEN_INTERNAL_LINK")
    assert bl["priority"] == "P1"
    assert bl["effort"] == "high"
    assert bl["broken_links"]  # Link-location evidence is carried into the task.
    assert bl["broken_links"][0]["link_path"]


def test_severity_filter(result):
    cfg = load_config(None)
    cfg["tasks_pipeline"]["include_severities"] = ["critical"]
    backlog = build_tasks(to_dict(result), cfg)
    assert {t["severity"] for t in backlog["tasks"]} == {"critical"}


def test_per_issue_grouping(result):
    cfg = load_config(None)
    cfg["tasks_pipeline"]["group_by"] = "issue"
    backlog = build_tasks(to_dict(result), cfg)
    # Per-issue grouping yields at least as many tasks as grouping by check.
    grouped = build_tasks(to_dict(result), load_config(None))
    assert backlog["summary"]["tasks_total"] >= grouped["summary"]["tasks_total"]


def test_markdown_renders(result):
    md = render_tasks_md(build_tasks(to_dict(result), load_config(None)))
    assert "# Audit Tasks" in md
    assert "P1" in md
    assert "/html/body/footer/nav/a[2]" in md  # tasks.md preserves XPath location evidence.


def _audit_with_occurrences(occurrences_count: int) -> dict:
    return {
        "run": {"project": "example.test", "generated_at": "2026-09-05T00:00:00Z"},
        "summary": {"health_score": 80},
        "issues": [
            {
                "id": "ISSUE-000001",
                "check": "BROKEN_INTERNAL_LINK",
                "severity": "critical",
                "source": "inlinks:Client Error (4xx) Inlinks",
                "message": "Internal link points to a 4xx URL",
                "target_url": "https://example.test/dead",
                "status_code": 404,
                "occurrences_count": occurrences_count,
                "fix_hint": "Replace the shared footer link.",
                "locations": [
                    {
                        "source_url": "https://example.test/source-a",
                        "anchor": "Old page",
                        "link_position": "Footer",
                        "link_path": "/html/body/footer/a[1]",
                    }
                ],
            }
        ],
    }


def test_min_occurrences_drops_low_frequency_issue_grouping():
    """#224: min_occurrences was never enforced when group_by == "issue"."""
    cfg = load_config(None)
    cfg["tasks_pipeline"]["group_by"] = "issue"
    cfg["tasks_pipeline"]["min_occurrences"] = 2
    backlog = build_tasks(_audit_with_occurrences(1), cfg)
    assert backlog["summary"]["tasks_total"] == 0


def test_min_occurrences_keeps_high_frequency_check_grouping():
    """#224: check grouping compared the issue-record count, not occurrences_count.

    One record with occurrences_count=100 must clear a min_occurrences=2
    threshold even though it is the only record in its group.
    """
    cfg = load_config(None)
    cfg["tasks_pipeline"]["group_by"] = "check"
    cfg["tasks_pipeline"]["min_occurrences"] = 2
    backlog = build_tasks(_audit_with_occurrences(100), cfg)
    assert backlog["summary"]["tasks_total"] == 1


def test_min_occurrences_same_meaning_both_grouping_modes():
    """#224: min_occurrences must exclude/retain identically regardless of group_by."""
    for group_by in ("check", "issue"):
        cfg = load_config(None)
        cfg["tasks_pipeline"]["group_by"] = group_by
        cfg["tasks_pipeline"]["min_occurrences"] = 5
        dropped = build_tasks(_audit_with_occurrences(4), cfg)
        assert dropped["summary"]["tasks_total"] == 0, group_by
        kept = build_tasks(_audit_with_occurrences(5), cfg)
        assert kept["summary"]["tasks_total"] == 1, group_by
