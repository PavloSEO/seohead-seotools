# Changelog

All notable public changes are documented here.

## Unreleased

- Restructure the operator skill into a controller directory (#111). `.claude/skills/`
  now has two tiers: 21 method skills, each covering one thing well, and `control/`,
  which decides which of them to run on a site nobody has looked at yet. The controller
  routes rather than restating, and carries five loadable sub-skills (scoping, rate and
  load, reading an audit, verifying, deliverables) and a three-file reference archive
  (defects found on live sites and what gave each away, which population each check
  describes, and what the toolkit cannot answer at all). The English-only gate and the
  doc-command gate now cover every Markdown file under a skill directory, not only
  `SKILL.md`.
- Add `tests/chains/`: a fixture site built out of the shapes that actually break chains —
  both slash forms of one URL, a body that is not valid UTF-8, a windows-1251 page, a
  masthead outside `<main>`, an off-host link, a robots-disallowed path — crawled over
  loopback, with seventeen assertions about the run as a whole rather than about any one
  module (#112). Four properties: conservation (a number does not change meaning as it
  travels), population (a finding is about a member of the set it describes),
  determinism (two crawls, two concurrency levels, one answer) and representation (a page
  says how it was measured). The population rules are `logscan`'s own, so a contradiction
  the scanner can name is a chain test that asserts it.
- `reconcile_sitemap` reports each URL as it was written rather than as it was normalised.
  Comparison still happens on the normalised key, but a finding that named a normalised
  form named a URL appearing nowhere in the crawl — unactionable for a reader, and
  indistinguishable to the anomaly scanner from a finding about a page never fetched.
- Add `docs/scenarios/`: ten end-to-end chains, each with the real commands in order, the
  artifact that comes out, what it costs, and what that chain cannot answer (#110). The
  rest of the documentation lists what the toolkit has; this describes what it does. Linked
  from the README above the tool list, so an agent evaluating the repository finds the
  chains before the inventory. Every command shown is executed against the fixture site by
  `tests/test_docs_commands_execute.py`, whose extractor and whose English-only and count
  gates now walk `docs/` at every level rather than only its top.
- Add `log-scan` (CLI) and `seo_log_scan` (MCP): read a finished run's own artifacts and
  report claims that cannot all be true at once (#109). Eight rules, each written from a
  defect that shipped past the whole test suite — a recorded size that disagrees with the
  file on disk, a text ratio over 100%, a check firing more often than there are pages to
  fire on, a finding about a URL the run never fetched, a canonical called a redirect while
  that URL answered 2xx in the same run, a summary that disagrees with its own rows, words
  counted on a zero-byte page, and pages measured two ways where only some say which. Each
  anomaly names both values and where each was read from. The CLI exits 2 when a run
  contradicts itself, so a pipeline stops instead of publishing the numbers.
- The cross-worker pacing test no longer measures the wall clock (#107). `_DispatchGate`
  now reads the crawl's injected clock instead of `time.monotonic()` directly, so the test
  drives it with a virtual clock that advances only when something sleeps: the dispatch
  instants are the crawler's own arithmetic and the assertion is exact. The old form
  compared real elapsed gaps against a 0.024s floor and failed on unchanged code whenever
  the machine was busy.
- Close the second half of the unwired-settings audit (#91). `http.headers` is merged into
  every request beside the credential headers; `speed.adaptive` gates the throttle's delay
  and concurrency adjustment (the timeout and server-error counters keep running — giving
  up is a separate mechanism from backing off); `discovery.hyperlinks.store` / `.crawl`,
  `discovery.external.store` and `discovery.redirects.crawl` now decide what the crawl
  records and what it follows. `discovery.canonicals.*`, `discovery.external.crawl` and
  `discovery.redirects.store` are removed rather than wired: they named capability the
  spider does not have (canonical-chasing, cross-host crawling) or state it cannot
  withhold, and a setting that appears in `--config-help` and the run manifest while
  changing nothing is worse than no setting. The coverage canary's exemption set is now
  empty: every `DEFAULTS` path changes an observable outcome and is named by a test.
- Detect the content area from the document's own semantics when nothing is configured
  (#96): `main`, then `[role="main"]`, then `article`, recording which one matched as
  `auto_main` / `auto_role_main` / `auto_article`. The previous default — the whole body
  minus the `nav` and `footer` tags — counted 126 template words out of 433 on a live
  WordPress post (29%), including a skip-to-content link, and that inflation feeds
  `THIN_CONTENT` and `LOW_TEXT_RATIO` in the same direction on every page of a template.
  `header` and `aside` join `nav` and `footer` in `DEFAULT_EXCLUDE_TAGS` for the fallback
  path. A configured selector still wins, and one that matches nothing still falls back to
  `fallback_default_body` rather than silently auto-detecting a different region.
- `URL_NOT_IN_SITEMAP` now compares pages with pages (#94). It compared a sitemap's URLs
  against every destination in the crawl's link graph, so on a live 124-page site it fired
  392 times — 362 image files a gallery links to directly, five off-host links, and 30 URLs
  the crawl never fetched — which was 74% of that report and buried the findings that were
  real. The observed side is now the pages a sitemap is supposed to declare: fetched, 2xx,
  HTML, same-host and indexable. `reconcile_sitemap` takes that population as a separate
  `comparable` argument, so `SITEMAP_ORPHAN` keeps asking about reachability against every
  link destination and cannot invent orphans; what was set aside is returned under
  `linked_not_comparable` rather than dropped.
- Fix the canonical checks on a site that serves both slash forms of a URL (#95).
  `norm_url` folds a trailing slash away on purpose, so a canonical written without one
  matches the page that has it — but the normalised index kept only one page per key, and
  a crawl of a typical WordPress site holds two: `/x` (301) and `/x/` (200). Reading
  whichever was inserted first made `CANONICAL_TO_REDIRECT` report 78 live pages whose
  canonical answers 200. `AuditContext` now exposes `pages_by_norm` with every page under
  a key, `page_by_norm` returns the variant that answered 2xx, and `CANONICAL_TO_REDIRECT`
  and `CANONICAL_NON_INDEXABLE` only fire when no variant contradicts them.
- Fix `size_bytes`: it is now the response body as it arrived on the wire, measured before
  the body is decoded (#99). It was measured from the decoded string, so every byte that is
  not valid UTF-8 became U+FFFD and re-encoded to three — a 739 KB WebP from a real crawl
  was recorded as 1.27 MB, and the inflation factor differs per file. Images, PDFs, fonts
  and HTML served in a legacy charset (windows-1251) were all over-counted, and so was the
  text ratio computed against that denominator. The HTTP cache stores the wire size with
  the entry, so a replayed page reports what the live fetch reported; its schema moves to
  `http_cache.v2` and v1 entries are re-fetched once rather than replayed without a size.
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

- Add the four static Lighthouse audits that need no browser and no third-party API
  (#59): `MISSING_CHARSET`, `MISSING_DOCTYPE`, `VIEWPORT_MISSING` and `NO_COMPRESSION`,
  each computed from evidence a crawl already holds. `content_encoding`,
  `meta_charset`, `doctype` and `viewport` join the normalized column vocabulary, so an
  SF export that happens to carry them as Custom Extraction columns feeds the same
  checks. Registry grows from 114 to 118 checks.
- Wire the ten remaining crawler settings that were validated, written into the run manifest, and
  described by `--config-help` but read by nothing (#63): `limits.max_response_bytes`,
  `speed.max_delay_seconds`, `robots.user_agent_token`, and `speed.stop_after_consecutive_timeouts`
  now configure behaviour that was previously hardcoded; `robots.unavailable_means_stop` now
  governs whether an unreachable or 5xx robots.txt stops the crawl or is treated as unrestricted
  (previously an unreachable robots.txt never stopped the crawl regardless of policy, while a 5xx
  one always did — now both are the same "unavailable" case, gated by the setting);
  `limits.max_url_length`, `limits.max_query_variants_per_path`, `http.retry_on_timeout`, and
  `discovery.follow_nofollow` are newly-implemented behaviour. `http.user_agent` is now applied to
  real requests instead of always sending the toolkit's default. Add `crawl-describe-settings`
  (CLI) and `seo_crawl_describe_settings` (MCP) so an agent can discover the configuration surface
  without a filesystem (#23).
- Add custom search (`tools/custom_search.py`) and custom extraction
  (`tools/custom_extract.py`) over an already-crawled corpus: presence/absence filters
  (raw source, visible text, a named CSS element, or an XPath node) and CSS/XPath/regex
  extractors, both reporting which representation (static markup vs. rendered DOM) they ran
  against. Absence is counted honestly: a page whose fetch failed is excluded from both the
  numerator and the denominator rather than counted as missing. Extraction runs each
  (document, extractor) pair under a wall-clock budget (`SIGALRM` on POSIX): a pathological
  expression aborts only that document, and the run still finishes.
- Add link position classification (`tools/link_position.py`): nav/header/sidebar/footer/content,
  by ordered rule over a link's ancestor path, reusing `content_area.py`'s notion of content
  rather than inventing a second one. Wired into `crawl/spider.py`'s link recording behind
  `link_position.classify` (default off — a position per link costs memory on a large crawl) and
  aggregated site-wide by `crawl/linkgraph.py`'s `inlink_composition`, which now feeds a new
  `INLINK_BOILERPLATE_ONLY` audit finding for pages linked only from boilerplate. Registry grows
  from 104 to 105 checks.
- Add eight post-crawl second-pass computations that only become answerable once a crawl is
  complete (issue #15): an internal link score computed from the `all_inlinks` edge graph
  (`LOW_LINK_SCORE`); a canonical target no hyperlink ever points to (`UNLINKED_CANONICAL`);
  `rel="next"` loop and unlinked-series detection (`PAGINATION_LOOP`,
  `UNLINKED_PAGINATION_SERIES`); hreflang reciprocity (`HREFLANG_MISSING_RETURN_LINK`);
  inlink-composition aggregates (`ONLY_NOFOLLOW_INLINKS`, `ONLY_NONINDEXABLE_SOURCE_INLINKS`);
  the concrete shortest discovery path from the crawl seed (`DEEP_DISCOVERY_PATH`); a
  self-computed mixed-content fallback (`INSECURE_SUBRESOURCE`); and near-duplicate clustering
  from stored page text (`NEAR_DUPLICATE`/`DUPLICATE_BY_HASH`), wiring `tools/duplicate.py` and
  `tools/content_area.py` into the audit for the first time. `ORPHAN_PAGE`, `SITEMAP_ORPHAN` and
  the two new "unlinked" checks are now withheld — reported as a named skip, not a finding — on a
  crawl the aggregator has marked partial, since "nothing links here" is unprovable on a
  truncated crawl. Registry grows from 104 to 114 checks.
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
