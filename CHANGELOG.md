# Changelog

All notable public changes are documented here.

## Unreleased

- Add `docs/TOOL_REFERENCE.md`, generated from the MCP tool definitions
  (`seohead/servers/tool_reference.py`, `scripts/generate_tool_reference.py`): every
  `seo_*`/`sf_*` tool's arguments with type and default, its cost (network/writes/
  idempotent/spend, read from its `ToolAnnotations` profile), and its own docstring's
  behavior and failure-mode notes. `tests/test_docs_drift.py` fails the build if it
  drifts from the tool definitions or is missing a tool.
- Add `tests/test_docs_commands_execute.py`: extracts every `seohead ...` command
  shown in README/docs/skills/examples (`scripts/doc_commands.py`) and runs each one
  offline, against a loopback fixture site (`tests/doc_fixtures/`) and materialized
  copies of `examples/`, asserting a clean exit. Commands that need real
  infrastructure (RDAP/DNS, a licensed SF binary, a paid provider credential, the
  never-returning `mcp` server) are at least parsed against the live argument parser.
  A documented command that no longer works now fails CI instead of shipping stale.
- Reshape all 21 technical workflow skills (`.claude/skills/*/SKILL.md`) into a
  shared shape: Trigger, Anti-trigger, Preconditions (as a checklist), the existing
  Workflow, Decision points, Definition of done (as a checklist), and Cost. Fix the
  stale command-coverage count at the bottom of `docs/SKILLS.md` (the real count,
  recomputed by scanning every skill file, is asserted by a new drift test).
- Fix several tool/test counts that had silently drifted from the real registries
  (a stale CLI command count in `docs/USAGE.md`/`docs/COMPARISON.md`/`README.md`/
  `docs/TESTING.md`, a stale MCP tool count in `docs/TOOLS.md`, a stale tool-reference
  count in `docs/README.md`, and the offline test count) and pin the fixed ones with
  a regression test (`test_stale_tool_counts_do_not_reappear`).

- Audit the crawl registry against an external technical-SEO checklist and close eight cheap,
  verified gaps: five hreflang checks (invalid language/region codes, missing self-reference,
  missing x-default, duplicate entries, non-canonical targets), two robots directives
  (`notranslate`, `unavailable_after`), and canonical URLs containing a fragment. Registry grows
  from 96 to 104 checks. See `docs/CHECKLIST_AUDIT.md`.
- Add `asset-weight-check`: fetches a page's linked CSS/JS and reports
  render-blocking resources, oversized files, duplicate libraries (by content
  hash), missing minification, missing `font-display`, legacy polyfilled JS,
  and missing compression/long-lived caching.
- Add `crawl-site --sitemap <url>` (and `sitemaps.auto_discover` in `--config`): seed the native
  crawler from a sitemap's declared URLs, follow links from each, and reconcile the declared and
  observed sets into `audit.json`'s `summary.sitemap`, under the same `SITEMAP_ORPHAN` /
  `URL_NOT_IN_SITEMAP` check ids the Screaming Frog pipeline already reports.
- Add `crawl-site --config-help`, generated from `seohead/crawl/config.py`, and hide `--max-depth`
  and `--min-delay` from `--help` (still accepted) so the flag surface stops growing with every
  crawler setting.
- Split technology fingerprinting into a fetch step and a pure `analyze_tech` step,
  capture analytics/tag-manager ids instead of only names, and add a `tag_coverage`
  report that groups presence by URL template and stamps how each page was measured.
- Resolve redirect chains and loops as a second pass over a finished crawl's own
  redirect targets, so `REDIRECT_CHAIN`/`REDIRECT_LOOP` no longer require the native
  Screaming Frog Redirect Chains report — a light-profile export or a `crawl-site` run gets
  the same findings for free.
- Add a configurable content area (`content_area.py`) that scopes word count to
  the main region, excluding navigation and footer by default, without
  affecting link discovery; the resolved strategy is reported per page.
- Separate exact from near duplicates in `duplicate.py`: exact matches are
  hashed from extracted text (not raw bytes) and excluded from near-duplicate
  clusters, and comparisons default to indexable pages only.
- Add a boilerplate-consistency report (`boilerplate_report.py`) that hashes
  header/nav/footer per page and flags minority template groups.
- Add dependency-free Markdown extraction (`markdown_extract.py`): a
  content-area-only rendering and a full-document one.
- Write down a naming convention (`docs/NAMING.md`) and resolve the module-basename collisions
  and process-named test files it found; no CLI command, handler, or MCP tool name changed.
- Add community, citation, and no-key agent onboarding files.
- Add the permissioned `analytics-console-review` workflow skill and three practical recipes.
- Document support for the current `3.x` security line.
- Require TLS 1.2 or newer and pin direct certificate probes to prevalidated public addresses.

## 3.0.0 — first public snapshot

- One Python package with 42 shared CLI/MCP tools.
- Five additional Screaming Frog MCP tools and a 96-check crawl analyzer.
- Domain, CDN, technology, security, mirror, regional, bot, and backlink reconnaissance.
- Schema.org validation and connected graph generation.
- Bounded sitemap-based site evidence and XLSX, DOCX, CSV, Markdown, and JSON reports.
- Optional Wordstat, Yandex SERP, Arsenkin, Metrika, and DataForSEO integrations.
- Twenty-one technical workflow skills and seven packaged SEO playbooks.
- Local stdio MCP and Docker support; no GUI, hosted API, or telemetry.
- Evidence-led public README with reproducible synthetic audit, task, interface, and report visuals.
- History-free public release boundary and explicit third-party notices.
