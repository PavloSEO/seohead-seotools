---
name: sf-analyzer
description: >-
  Machine-readable SEO audit from a Screaming Frog crawl. Use when the user asks
  to analyze a .seospider file or Screaming Frog exports, find broken links and
  where they appear in the DOM (source, anchor, position, XPath), check a sitemap
  for stale lastmod values / 3xx-4xx entries / discrepancies with the site, detect
  oversized HTML pages (size anomalies), identify "two H1s: which ones and where,"
  or generate audit.json + audit.md for a site. Triggers: screaming frog,
  .seospider, SF export, internal_all.csv, sitemap audit, broken links, audit.json,
  crawl SEO audit.
---

# SF Analyzer — SEO Audit from Screaming Frog

Converts a single Screaming Frog crawl (19.x) into two machine-readable reports:
`audit.json` (a contract for downstream analysis/LLMs) and `audit.md` (for humans).
Extracts as much information as possible from SF panels, precisely locates links
(where each link appears, where it points, and where it is in the DOM), and adds
checks that SF itself does not flag (HTML size anomalies, sitemap discrepancies,
and stale `lastmod` values).

## When to Use
- "Run an SEO audit on this crawl / `.seospider` file / set of SF exports";
- "Find broken links and where they appear in the DOM";
- "Check the sitemap for stale lastmod values, 4xx/3xx entries, and discrepancies";
- "Which pages are abnormally large?" or "There are two H1s—which ones and where?";
- "Create an audit.json file for the site."

## Two Input Modes
- **Mode B (default; SF not required):** a folder containing CSV/XLSX files
  exported manually from SF. Even `Internal:All` alone is sufficient. This is a
  self-contained workflow.
- **Mode A (requires an SF license + CLI):** the tool launches SF in headless mode
  for a `.seospider` file, domain, or URL list and exports the required
  tabs/bulk exports/reports.

> A `.seospider` file is Java-serialized data (it cannot be parsed directly). It
> requires either the licensed SF CLI (Mode A) or a manual CSV export (Mode B).

## Workflow
1. **Determine the input.** Get the path to a `.seospider` file or export folder,
   or get the domain. If it is unclear, clarify the mode (A/B) and profile
   (`lite`/`full`).
2. **Check the environment → locate SF.** Run `seohead sf doctor`; it searches for
   the SF CLI **everywhere**: the `--sf-cli` flag, the `$SF_CLI` and
   `$SCREAMINGFROG_CLI` variables, `config.json` (`sf_cli.path`/`search_paths`), the
   system `PATH`, and standard installation directories via glob patterns:
   `C:\Program Files*\Screaming Frog SEO Spider\*Cli.exe` (which catches both `(x86)`
   and versioned installations),
   `/Applications/Screaming Frog SEO Spider.seohead/sf/...`, `/usr/bin`, `/opt`, and
   `/snap`. If SF is found, use Mode A (`--crawl <domain>`). If it is not found,
   provide the path (`--sf-cli "...\ScreamingFrogSEOSpiderCli.exe"` or `SF_CLI=...`)
   or switch to Mode B (`reference/sf_cli_cheatsheet.md`). Mode A requires an SF
   **license**.
3. **Run the audit.** Full automated workflow from a domain (SF crawls the site →
   report → tasks):
   ```bash
   # Mode A — provide a domain and get everything (requires SF + a license)
   seohead sf run --crawl https://example.com --sitemap https://example.com/sitemap.xml --out report --tasks
   # From a saved crawl
   seohead sf run --load-crawl site.seospider --profile full --out report --tasks
   # Mode B — use existing exports (SF not required)
   seohead sf run --exports-dir ./exports --out report --tasks
   ```
   For MCP, use the `sf_audit_run` tool. The thin wrapper is
   `scripts/run_audit.sh`.
4. **Read `audit.json`.** Give the user the health summary first, followed by the
   critical section (broken links with DOM locations, and 4xx/5xx entries in the
   sitemap). On request, provide details through `sf_audit_issues` (filter by
   `check`/`severity`).
5. **Attach the files** `audit.json` + `audit.md` for download.

Related skills: **sf-report** provides a human-readable report analysis;
**sf-tasks** provides a prioritized backlog (`seohead sf tasks` / MCP
`sf_audit_tasks`). MCP tools: `sf_audit_run`, `sf_audit_summary`, `sf_audit_issues`,
`sf_list_exports`, `sf_audit_tasks`.

## Interpretation
- Check registry and severity levels: `reference/checks.md`.
- `audit.json` contract: `reference/json_schema.md`.
- Exact SF CLI commands: `reference/sf_cli_cheatsheet.md`.

Load files from `reference/` as needed (progressive disclosure) to avoid bloating
the context.
