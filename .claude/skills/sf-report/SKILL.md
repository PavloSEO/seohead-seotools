---
name: sf-report
description: >-
  Produces a readable Markdown report from a Screaming Frog export: instead of merely
  "collecting and fixing," it formats an audit report that people can understand —
  health score, issues by severity, broken links with DOM location
  (source/destination/position/XPath), duplicates, heavy pages, and sitemap. Use when
  asked to "create a report from an SF export," "format a readable report," "prepare
  a client audit report," or "explain audit.json clearly." Triggers: Screaming Frog
  report, audit.md, readable report, export report, SEO report.
---

# SF Report — Readable Report from a Screaming Frog Export

Converts an SF export (CSV/XLSX) **or** an existing `audit.json` into a human-readable
`audit.md` and helps review it with the user. It uses the same engine as
`sf-analyzer`, but the goal here is not diagnostics for the sake of JSON; it is a
**clear report**.

## When to Use It
- "Create a readable report from this SF export";
- "Format an audit report for the client / developers";
- "Explain `audit.json` in plain language and identify what matters."

## Workflow
1. **Identify the input:** a directory containing SF exports (at minimum
   `Internal:All`) or an existing `audit.json`. If only a `.seospider` file is
   available, see `../sf-analyzer/SKILL.md` (this requires the SF CLI or a manual
   CSV export).
2. **Generate the report:**
   ```bash
   seohead sf run --exports-dir ./exports --out ./report --format md,json
   ```
   The generated `report/audit.md` is the readable report. If `audit.json` already
   exists, rebuild the Markdown with the same run when necessary.
3. **Review it with the user** according to the `audit.md` structure:
   - **Health summary** — health score, severity table, top issues, HTML weight;
   - **Critical** — broken links (table
     `Destination｜Source｜Anchor｜Position｜XPath`), 5xx responses, 4xx/5xx URLs in
     the sitemap, redirect loops;
   - **Warning** — duplicates (grouped), multiple H1 elements with their text,
     canonical issues, thin content, sitemap mismatches, heavy HTML (× median);
   - **Notice** — URL hygiene, meta-field lengths;
   - **Sitemap & robots** — sitemaps, mismatches, `lastmod` distribution.
4. **Highlight what matters:** start with critical issues and the most frequent
   problems (`summary.by_check`); explain the impact and what to fix (the `fix_hint`
   field). Do not dump the entire list — highlight the priorities and attach the
   rest as a file.
5. **Attach** `report/audit.md` (+ `audit.json`) for download.

## Interpretation
- Check registry and severity levels — `../sf-analyzer/reference/checks.md`.
- `audit.json` contract — `../sf-analyzer/reference/json_schema.md`.
- If tasks/a backlog are needed from the report, switch to the `sf-tasks` skill.
