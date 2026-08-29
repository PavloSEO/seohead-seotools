---
name: sf-tasks
description: >-
  Builds a prioritized task backlog from a Screaming Frog export or audit.json, with
  a configurable pipeline (which severities to include, grouping by issue type or
  URL, P1/P2/P3 priorities, effort estimates, and limits). For broken links, each
  task includes the location (source/destination/position/XPath). Use when asked to
  "create tasks from the export," "build an audit backlog," "prepare developer
  tasks," or "create a task table from audit.json." Triggers: tasks from an audit,
  SEO backlog, tasks.md, task pipeline, Screaming Frog Scrum backlog, what to fix
  from an export.
---

# SF Tasks — Task Backlog from an Audit

Converts an audit (`audit.json`) into a ready-to-use **backlog**: `tasks.json`
(machine-readable) and `tasks.md` (a checklist organized by priority). The pipeline
is configurable: what to include, how to group items, and which priorities and
effort estimates to assign.

## When to Use It
- "Create tasks from this export / audit";
- "Build a backlog for developers" or "What should be fixed first?";
- "I need tasks.md / a prioritized task list."

## Workflow
1. **Obtain the audit.** If `audit.json` is available, go directly to step 3. If
   only SF exports are available, run the audit first:
   ```bash
   seohead sf run --exports-dir ./exports --out ./report
   ```
2. **(Optional) Configure the pipeline** in `config.json` → `tasks_pipeline`:
   - `include_severities` — which levels to include (all by default);
   - `group_by` — `check` (one task per issue type) or `issue` (by URL);
   - `priority_map` — severity → `P1/P2/P3`; `effort_map` — severity → effort;
   - `max_urls_per_task`, `min_occurrences`, `include_checks`/`exclude_checks`.
3. **Build the tasks:**
   ```bash
   seohead sf tasks --json ./report/audit.json --out ./report --config config.json
   # Or generate them together with the audit in a single command:
   seohead sf run --exports-dir ./exports --out ./report --tasks
   ```
   Through MCP, use the `sf_audit_tasks {json_path, out, config?}` tool.
4. **Deliver the result.** `tasks.md` is a checklist organized by `P1/P2/P3` with
   a "how to fix" field; for broken links, it includes a
   `destination ← source · position · XPath` list. Discuss P1 first, estimate the
   total scope (`summary.by_priority`), and attach `tasks.json` for the tracker.

## Task Format (`tasks.json`)
`id`, `check`, `priority` (P1/P2/P3), `severity`, `effort`, `title`, `fix_hint`,
`affected_count`, `occurrences`, `urls[]` (subject to the limit), and, for links,
`broken_links[]` with location details. Groups and priorities are deterministic, so
the backlog can be diffed between runs.

## Related Skills
- If no audit has been generated from `.seospider`/exports yet, use the
  `sf-analyzer` skill.
- If a human-readable review is needed instead of tasks, use the `sf-report` skill.
- Check registry (everything that can be detected) —
  `../sf-analyzer/reference/checks.md`.
