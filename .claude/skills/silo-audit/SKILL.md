---
name: silo-audit
description: >-
  Determines whether a website has a silo architecture (topical clusters, hubs, URL
  depth, internal linking, and semantic coverage) or is a flat brochure site. Uses a crawl's
  audit.json (crawl_depth, inlinks, is_in_sitemap, summary.sitemap) from either native
  crawl-site or sf-analyzer — both producers share the same schema — and the
  reference/silo-architecture.md guide. Produces a verdict of
  chaos / basic silo / extended silo plus a list of gaps. Triggers on: silo or not silo,
  silo architecture, website structure, topical clusters, semantic coverage, flat
  structure, website architecture, topical authority, site structure audit, silo
  structure, and topical map.
---

# Silo Audit — Does the Website Have a Silo Architecture?

This is an agent analysis layer **ON TOP OF** Screaming Frog: SF knows depth and inlinks,
but it does not judge whether URLs form topical silos with hubs or whether semantic
coverage is complete. This skill builds a URL tree, calculates structural metrics, and
returns a verdict of **chaos / basic silo / extended silo**. The theory—3 levels, extended
silos, the filter matrix, cross-links, E-E-A-T, and coverage of 5–15% / 20–30% /
70–90%—is in `reference/silo-architecture.md`; load it before evaluating a website.

## Trigger
- "Do we have a silo or not?" and "Evaluate the website structure/architecture."
- "Are there topical clusters?" and "Is semantic coverage complete?"
- "Is the website flat or just a brochure site?" and "Have we reached topical authority?"
- "Site structure audit" and "silo structure."
- Frontmatter triggers: silo or not silo, silo architecture, website structure,
  topical clusters, semantic coverage, flat structure, website architecture,
  topical authority, site structure audit, silo structure, topical map.

## Anti-trigger
- The question is about individual crawl issues (broken links, duplicates, thin
  content) rather than structure — that is `sf-report`/`sf-tasks` reading the same
  `audit.json`, not this skill.
- No `audit.json` exists yet from either producer and there is also no sitemap to fall
  back on — there is no URL tree to build. Run a crawl first (native `crawl-site` or
  `sf-analyzer`), or obtain a sitemap URL from the user.
- The ask is "check robots.txt / crawlability," not "is the structure a silo" —
  crawl blocking and URL architecture are different axes; use `robots-audit`.
  A page can be perfectly crawlable and still be architecturally flat.
- The deliverable is a client-facing narrative report, not a structural verdict —
  hand the silo verdict and gap list to `sf-report`/`site-report` to fold into a
  full report rather than presenting this skill's output as the whole deliverable.

## Preconditions
- [ ] An `audit.json` is available (preferred — gives `crawl_depth`, `inlinks`,
  `is_in_sitemap`, `summary.sitemap`) from **either** producer: native
  `crawl-site` (see `control`) or `sf-analyzer` — both share the same
  aggregator and carry the same fields, so an existing native run already
  satisfies this precondition without restarting collection through SF. A
  fetchable `sitemap.xml` is the fallback when neither exists yet.
- [ ] `reference/silo-architecture.md` has been loaded before scoring, since the
  chaos/basic/extended thresholds and hub/cluster definitions live there, not in
  this file.
- [ ] The niche's expected intent set (catalog, industries, glossary, cases,
  E-E-A-T pages, etc.) is known well enough to judge semantic coverage — otherwise
  the coverage percentage in step 3 has no denominator to compare against.

## Workflow
1. **Obtain crawl data.** Reuse an existing `audit.json` if one already exists — from native
   `crawl-site` (`../control/SKILL.md`) or from `sf-analyzer` (`../sf-analyzer/SKILL.md`); both
   producers share the aggregator, so declare specifically which of `crawl_depth`/`inlinks`/
   `is_in_sitemap`/`summary.sitemap` are actually missing before running a new crawl through
   either one. Only run a fresh crawl if none exists. Otherwise, work from the sitemap:
   `curl -s https://example.com/sitemap.xml | grep -oE '<loc>[^<]*</loc>' | sed -E 's#</?loc>##g'`
   (POSIX `-E`/`sed`, not GNU-only `-P`, so it also runs on macOS's stock BSD grep).
   Build the path tree from indexable HTML in `pages[]`; exclude `_next/`, `.js`, and
   images.
2. **Structural metrics** calculated in Python from `pages[].metrics`:
   - URL path depth: `len([s for s in urlparse(u).path.split('/') if s])`. Calculate
     both the **maximum** and **median**. A flat structure has a median of ≤1 and almost
     everything at L0/L1. A silo typically has L1 section hubs → L2 internal pages, with
     L3 in an extended silo.
   - **Hub pages**: for every L1 prefix such as `/services/` or `/industries/`, check
     whether its own `/<prefix>/` index page links to child pages. Count children per
     prefix; a cluster is viable when it has ≥3–5 pages beneath a shared hub.
   - SF **crawl_depth** (`metrics.crawl_depth`): calculate the maximum and median. A
     depth beyond 4–5 clicks indicates a diluted silo or poor internal linking.
   - **Orphan rate**: divide the number of `pages` with `metrics.inlinks == 0` or
     `unique_inlinks == 0` by the total number of indexable pages. A rate above 10–15%
     indicates a structure with significant gaps.
   - **Breadcrumbs**: look for `BreadcrumbList` in SF structured data or `<nav>`
     breadcrumbs in saved HTML. Their presence confirms the silo hierarchy.
   - **Cross-cluster links**: use `issues[].locations`/inlinks to calculate the share of
     links whose `source_url` and `target_url` belong to different L1 clusters. A healthy
     silo keeps authority within each cluster but has *some* controlled cross-links; see
     the reference. It should have neither zero cross-links nor chaotic “everything to
     everything” linking.
   - **Sitemap vs. crawl**: use `summary.sitemap` to compare `urls_in_sitemap` with
     `in_crawl_not_in_sitemap`. Coverage gaps indicate incomplete silo branches.
3. **Semantic coverage.** Use the set of L1 prefixes and headings (`metrics.title`, `h1`)
   to identify which intents are covered and which have obvious gaps:
   catalog/services · industries/applications · dictionary/glossary · cases/portfolio ·
   materials/blog hub · E-E-A-T pages (author/expert, about, methodology).
   A rough coverage percentage is covered intents divided by expected intents for the
   niche. Compare it with the reference thresholds: **5–15% — chaos**, **20–30% — basic
   silo**, and **70–90% — extended silo**.
4. **Verdict.** Consolidate the metrics into one of three classes:
   - **chaos/brochure site** — flat structure with median depth ≤1, no hubs, a high
     orphan rate, and 5–15% coverage;
   - **basic silo** — L1 hubs, clusters of 3–5+ pages, breadcrumbs, and 20–30% coverage;
   - **extended silo** — L3 depth, a filter matrix, glossary + cases + E-E-A-T,
     controlled cross-links, and 70–90% coverage.
   Then provide a **gap list**: which hubs, clusters, and intents are missing; where
   orphan nodes occur; where cross-cluster links cause the silo to “leak”; and what to
   add—specific sections and hub pages—to reach the next level.

## Decision points
- **Metrics fall in different classes.** A site might have basic-silo depth/hubs
  but chaos-level coverage (or vice versa). Do not average the classes: state each
  metric's class explicitly and let the lowest-scoring dimension drive the overall
  verdict, since a gap in one dimension (e.g. no E-E-A-T pages) is still a real gap
  regardless of how good the URL depth looks.
- **Cross-cluster link share is ambiguous on its own.** Zero cross-links and a
  chaotic "everything links to everything" pattern are both bad, but for opposite
  reasons (isolated silos vs. no silo boundaries at all). Check the *distribution*
  of cross-links against the reference guide's controlled-cross-link pattern
  before calling either extreme a defect.
- **`sitemap.xml` fallback vs. `audit.json`.** Without a crawl, the sitemap gives
  you the URL list but not `inlinks`/`crawl_depth`/orphan data — say explicitly
  which metrics could not be computed in fallback mode rather than presenting a
  partial verdict as if it were complete.
- **Coverage percentage depends on the expected-intent list.** This list is a
  judgment call per niche (an e-commerce site and a SaaS site expect different
  intents). State which intents were assumed as "expected" before reporting a
  coverage percentage, so the number is reproducible rather than asserted.

## Definition of done
- [ ] Maximum and median URL depth, `crawl_depth`, and orphan rate are all
  computed and stated (or explicitly marked unavailable in sitemap-only fallback).
- [ ] Every L1 prefix has been checked for a hub page and a child count, feeding
  the cluster table.
- [ ] A single chaos/basic/extended verdict is given, with the metric(s) that
  drove it named explicitly (see Decision points).
- [ ] A prioritized gap list exists naming missing hubs/clusters/intents, not
  just the current-state metrics.

## Cost
No new `seohead <command>` calls of its own beyond what already produced `audit.json` —
native `crawl-site` or `sf-analyzer` — this skill only reads that file (or, in fallback
mode, makes one `curl` request to `sitemap.xml`). All structural-metric computation is
local Python over `pages[]`/`issues[]`; no paid API involved. Cost scales with the
producing crawl, not with anything this skill does independently.

## What to Deliver to the User
- The architecture class (chaos / basic / extended) plus an evidence-based semantic
  coverage percentage.
- A cluster table: L1 prefix · hub (yes/no) · number of children · orphans · breadcrumbs.
- Key figures: maximum/median depth, maximum `crawl_depth`, orphan rate, share of
  cross-cluster links, and sitemap coverage.
- A prioritized list of gaps and what to add to raise the silo level.

Related skills: **control** (native `crawl-site`) and **sf-analyzer** each provide
`audit.json` and crawl data; **sf-report** provides a human-readable analysis; **sf-tasks**
turns silo gaps into a backlog.
Load the theory from `reference/silo-architecture.md` through progressive disclosure.
