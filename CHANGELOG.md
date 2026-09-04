# Changelog

All notable public changes are documented here.

## Unreleased

- Add `crawl-site --config-help`, generated from `seohead/crawl/config.py`, and hide `--max-depth`
  and `--min-delay` from `--help` (still accepted) so the flag surface stops growing with every
  crawler setting.
- Split technology fingerprinting into a fetch step and a pure `analyze_tech` step,
  capture analytics/tag-manager ids instead of only names, and add a `tag_coverage`
  report that groups presence by URL template and stamps how each page was measured.
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
