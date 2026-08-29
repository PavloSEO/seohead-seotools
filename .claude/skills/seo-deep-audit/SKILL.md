---
name: seo-deep-audit
description: >-
  SINGLE ENTRY POINT and orchestrator for a complete domain SEO audit. Triggers when a site/domain
  is provided with a request to inspect/analyze/check it — WITHOUT a specified scope. By default,
  it runs the MAXIMUM: reconnaissance (domain/hosting/CMS), a complete Screaming Frog crawl (all
  96 checks), agent-level analysis (robots, JS rendering, silo structure, H1–H6), and a consolidated
  report + task backlog. Use a narrow analysis only when the scope is stated explicitly ("only
  robots," "quick/lite," "no rendering"). Use for: "analyze the site," "perform an SEO audit of
  the domain," "inspect the entire site," "what is wrong with the site," "audit this domain,"
  "full SEO audit," or when the user simply provides a URL/domain for analysis. Triggers: analyze
  site, perform audit, full SEO audit, inspect domain, check site, what is wrong with the site,
  audit site, analyze domain, deep SEO audit, full audit, site audit.
---

# SEO Deep Audit — orchestrator: provide a domain -> get everything

One entry point for a complete audit. When given a domain **without a specified scope, work at
maximum depth**: run the entire chain of skills and tools yourself, collect everything, and
consolidate it into one report + task plan. Narrow the work only when EXPLICITLY instructed
("only robots," "quick," "lite," "no rendering," "check only headings"). The map of "which tool
retrieves what" is in the `sf-boundaries` skill.

> If you need a plan for **exactly what** to collect before expensive runs, start with
> `audit-roadmap` (Recon lite -> roadmap with priorities, scale, site type, and YAGNI), and then
> this skill executes the roadmap.

## Default rule
- **No scope clarification -> MAX.** Run every phase below.
- **Explicitly narrowed scope -> only that scope.** "only sitemap" -> only the sitemap portion;
  "quick/lite" -> `--profile lite` + skip expensive agent-level phases.
- Never ask "should I do a full audit?" — a full audit is the default. Clarify only what makes
  progress impossible (no domain; SF is not installed and no exports are available).

## Pipeline (all phases by default)
**Phase 0 — Reconnaissance (what kind of site is this?).** The `seo-recon` skill — three toolkit
tools:
```bash
seohead domain-profile --domain <domain>   # registration, DNS, ASN, geography, TLS, flags
seohead cdn-check       --url https://<domain>   # CDN + actual cache behavior, HTTP/2-3, TTFB
seohead tech-detect     --url https://<domain>   # CMS/framework/server, analytics, pixels
```
Remember the stack: if `tech-detect` found an SPA/Next.js/Nuxt, mark JS rendering as required
(Phase 2). Some findings from `domain-profile.flags` and `cdn-check.findings` go directly into
the report.

**Phase 1 — Crawl (core, all 96 checks).** Check the environment first: `seohead sf doctor`.
```bash
seohead sf run --crawl https://<domain> --out report --tasks
```
The **full** profile is the default (maximum coverage), and the sitemap is automatically obtained
from robots. If the output contains many `skipped` results because SF modules are disabled
(MIXED_CONTENT/STRUCTURED_DATA/SPELLING/DOM_*), enable them once through the `sf-config` skill
(create `audit.seospiderconfig`); the tool will pick it up automatically. If SF/a license is not
available, request exports and use mode B (`--exports-dir`); see `sf-analyzer`/`sf-config`.

**Phase 2 — Agent-level (what SF cannot see).** In parallel or sequentially:
- `robots-audit` — analyze robots.txt for junk/harmful directives (+ fix diff). Compare the
  results with `IMPORTANT_URL_BLOCKED_BY_ROBOTS` from the audit (live pages blocked by robots).
- `js-render-check` — raw HTML (view-source) vs rendered output: what appears only after JS.
  Required if Phase 0 found an SPA/Next.js, or if the crawl ran without JS Rendering.
- `silo-audit` — silo or not: clusters, hubs, depth, coverage (using `audit.json` + sitemap).
- `heading-outline` — complete H1–H6 structure (on key templates: home, category, product
  page/article — not on all 1,000 pages, but on one of each type + problematic pages from the
  audit).
- `security-audit` — security headers (HSTS/CSP/…), version leaks, cookie flags, http->https:
  `seohead security-check --url https://<domain>`. This affects trust and HTTPS ranking.
- `schema-graph` — structured data: page type, connected `@graph`, two-layer JSON-LD validation
  (vocabulary + rich results), and what is missing for the snippet. Run it on the same templates
  as heading-outline (home / category / product page / article):
  ```bash
  seohead schema-build --url https://<domain>/<template>   # type + proposed graph + diff
  seohead schema-check --url https://<domain>/<template>   # validate what already exists
  ```
  State the finding about the **template** ("product pages have no offers"), not about an
  individual URL.
- `duplicate-audit` — near-duplicate and thin pages: collect page text (from the SF crawl or
  sitemap+parse) and run `seohead duplicate-check --input '{...}'` (simhash + LSH). It finds
  duplicate clusters without pairwise comparison — critical for sites with thousands of pages.
- `geo-aeo-audit` — visibility in AI answers: `seohead ai-bots-check` (which robots.txt permits
  among GPTBot/ClaudeBot/Perplexity/Google-Extended) + `seohead llms-txt-check` (score for
  /llms.txt). Content citability is an editorial assessment by template.

**Phase 3 — Synthesis.** `sf-report` — a human-readable analysis of `audit.json`; merge the Phase
0 and Phase 2 findings into it. `sf-tasks` — a prioritized backlog; add tasks from agent-level
findings (robots fix, SSR/prerendering, completing silo clusters, heading hierarchy).

## What to deliver to the user (one consolidated package)
1. **Site profile** (reconnaissance): domain/age, hosting/CDN, CMS/stack, risk flags.
2. **Health & critical:** health score, critical section (broken links with DOM localization,
   5xx, 4xx/5xx in the sitemap, important URLs blocked by robots).
3. **Rendering:** SSR or content/links/meta available only after JS (verdict + indexing risk).
4. **Structure:** silo / basic / extended + gaps; heading hierarchy.
5. **Sitemap & robots:** sitemap-to-crawl alignment, stale lastmod values, harmful directives.
6. **Security:** security headers (A–F grade), version leaks, http->https.
7. **Structured data:** page types, JSON-LD graph connectivity, dangling `@id` values, rich-result
   eligibility and missing required fields; an explicit note that FAQPage/HowTo no longer produce
   snippets (but remain useful for AI).
8. **Prioritized task plan** (`tasks.md`) + downloadable `audit.json`/`audit.md` files.

## Graceful degradation (without errors)
If SF is unavailable, use mode B or report that `--crawl` requires SF
(`sf-config`/`sf-analyzer`). If the network is unavailable for reconnaissance/rendering, skip
those phases and mark them "not checked" in the report; do not crash. A `skipped` check is honest
(no data/module), not zero.

## Integrations
Core: `sf-analyzer` · `sf-report` · `sf-tasks` · `sf-config`. Agent-level: `seo-recon` ·
`silo-audit` · `js-render-check` · `heading-outline` · `robots-audit` · `security-audit` ·
`schema-graph` · `duplicate-audit` · `geo-aeo-audit`.
"SF or elsewhere" router: `sf-boundaries`. Link profile check: `backlinks-check`.
