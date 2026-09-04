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
