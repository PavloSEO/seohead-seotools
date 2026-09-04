# Changelog

All notable public changes are documented here.

## Unreleased

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
- Wire `markdown_extract` and `boilerplate_report` into the CLI and MCP surface as
  `markdown-extract`/`seo_markdown_extract` and `boilerplate-report`/`seo_boilerplate_report`
  (47 core tools, up from 45), and add the `only_indexable` flag `duplicate_check` already had
  at the handler layer to `seo_duplicate_check`'s MCP signature, where it had been missed.
  Rescope `citability-check`'s URL path from the parser's whole-document `text` field (a single
  collapsed line with no paragraph or heading breaks at all) to `markdown_extract`'s content-area
  Markdown, fixing both the boilerplate dilution the issue raised and a latent bug where the flat
  text silently zeroed the Answer-Blocks and Structure-Quality dimensions for every live URL.
  Left unscoped, deliberately: the parser's `text` field itself, still whole-document, because
  `page_facts.py`'s schema-evidence extraction (`sameAs` social links, breadcrumbs, price/rating
  regexes) depends on facts that legitimately live in header/footer widgets the content area
  excludes; and the Screaming-Frog-driven `THIN_CONTENT`/`LOW_TEXT_RATIO` checks in
  `sf/core/rules.py`, whose `word_count`/`text_ratio` come from Screaming Frog's own export
  columns — third-party data the toolkit has no raw HTML to rescope without re-fetching every
  page, defeating the zero-request offline-corpus design of the SF audit path. The toolkit's own
  crawler (`crawl-site`) already inherits the content-area scoping for free, since its word count
  reads straight from `parser.parse_html`.
- Write down a naming convention (`docs/NAMING.md`) and resolve the module-basename collisions
  and process-named test files it found; no CLI command, handler, or MCP tool name changed.
- Add community, citation, and no-key agent onboarding files.
- Add the permissioned `analytics-console-review` workflow skill and three practical recipes.
- Document support for the current `3.x` security line.
- Require TLS 1.2 or newer and pin direct certificate probes to prevalidated public addresses.
- Add an HTTP response cache for `crawl-site` (`seohead/crawl/cache.py`, opt-in via
  `cache.mode` — default `off`, so no side effect appears behind a default): real HTTP freshness
  semantics (`max-age`/`Expires`, `ETag`/`Last-Modified` revalidation, `Vary`-aware variants,
  `no-store`/`no-cache` honoured), a `replay` mode for debugging that is stamped in the manifest
  and never the default, and an `invalidate` flag for an explicit hard refresh. Every fetched
  page carries `cache_status` (`hit`/`revalidated`/`miss`); the run carries `cache_stats` and
  `cache_replay` in both the handler output and `audit.json`'s `run` block, so a report built
  partly from cache says so. A cache hit costs no request and consumes no throttle delay or
  concurrent dispatch-gate slot either — the wait is issued from inside `fetch_one` itself, only
  once a real network round trip is actually about to happen.
- Add journal-driven reuse to `seohead/runlog.py` (`SEOHEAD_REUSE_POLICY`, a per-tool maximum
  age in seconds; default empty, meaning nothing is ever reused). A configured, still-fresh,
  successful prior answer is returned instead of calling the tool again, marked `reused: true`
  with `reused_from_ts` in both the result and the new journal entry it still writes — freshness
  is always measured against when the value was actually fetched, never extended by reuse itself.

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
