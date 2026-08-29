---
name: silo-audit
description: >-
  Determines whether a website has a silo architecture (topical clusters, hubs, URL
  depth, internal linking, and semantic coverage) or is a flat brochure site. Uses an
  sf-analyzer crawl (audit.json: crawl_depth, inlinks, is_in_sitemap,
  summary.sitemap) and the reference/silo-architecture.md guide. Produces a verdict of
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

## When to Use It
- “Do we have a silo or not?” and “Evaluate the website structure/architecture.”
- “Are there topical clusters?” and “Is semantic coverage complete?”
- “Is the website flat or just a brochure site?” and “Have we reached topical authority?”
- “Site structure audit” and “silo structure.”

## Workflow
1. **Obtain crawl data.** You need `audit.json` from **sf-analyzer**; see
   `../sf-analyzer/SKILL.md`. If it is unavailable, run a crawl first. Otherwise, work
   from the sitemap: `curl -s https://example.com/sitemap.xml | grep -oP '(?<=<loc>)[^<]+'`.
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

## What to Deliver to the User
- The architecture class (chaos / basic / extended) plus an evidence-based semantic
  coverage percentage.
- A cluster table: L1 prefix · hub (yes/no) · number of children · orphans · breadcrumbs.
- Key figures: maximum/median depth, maximum `crawl_depth`, orphan rate, share of
  cross-cluster links, and sitemap coverage.
- A prioritized list of gaps and what to add to raise the silo level.

Related skills: **sf-analyzer** provides `audit.json` and crawl data; **sf-report**
provides a human-readable analysis; **sf-tasks** turns silo gaps into a backlog.
Load the theory from `reference/silo-architecture.md` through progressive disclosure.
