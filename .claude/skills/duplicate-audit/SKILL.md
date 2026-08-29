---
name: duplicate-audit
description: >-
  Finds near-duplicate and thin pages on a site: filtered pagination, copied content,
  utility duplicates, and weakly differentiated product pages. It works with a list of page
  texts (from a Screaming Frog crawl, sitemap+parse, or a prepared list) and groups similar
  pages using simhash + locality-sensitive hashing, without pairwise comparison, so it scales
  to tens of thousands of pages. Triggers on: "find duplicates," "near duplicate,"
  "duplicate content," "thin pages," "thin content," "check uniqueness,"
  "identical pages," "similar pages," "cannibalization," and "catalog duplicates."
---

# Duplicate Audit — Near-Duplicate and Thin Pages on a Large Site

Comparing N pages pairwise is O(N²); for 10,000 pages, that means 50 million checks. This
skill uses **simhash + LSH**: each page becomes a 64-bit fingerprint, similar pages land in
the same "bands," and only candidates are compared. The similarity threshold is configurable.

## When to Use It
- Duplicates are suspected on a large site (pagination, filters, copied content, utility pages).
- "Thin pages" / thin content: you need to find pages with little content or identical pages.
- Search-result cannibalization: find pages competing for the same intent.

## Workflow

**Step 1. Collect page text.** There are three sources; choose the one available:
- **From an SF crawl** (recommended for a large site): take `internal_html.html`
  (or `all_bodytext` from the normalized export) and map each URL to its visible text.
- **From sitemap + parse** (without SF): run `seohead sitemap-crawl --url .../sitemap.xml`,
  then run `seohead parse` on the URL list, collecting each page's `text` field.
- **Prepared list**: ``[{"id": "<url>", "text": "..."}]``.

**Step 2. Find duplicate clusters.**
```bash
seohead duplicate-check --input '{"items":[{"id":"https://example.com/a","text":"..."},
  {"id":"https://example.com/b","text":"..."}], "threshold": 0.92}'
```
- `threshold` 0.92 (the default) means nearly identical. Lower it to 0.85 for "highly
  similar" pages, or raise it to 0.97 for "strict duplicates."
- In the response, `clusters[]` contains groups of ≥2 pages, with pairwise similarity
  within each group and the group's `min_similarity`; `candidate_pairs_checked` is the
  number of pairs checked exactly (after LSH filtering).

**Step 3. Interpret the results.**
- A cluster with `min_similarity = 1.0` contains exact duplicates (often utility pages or
  pagination). Resolution: canonical, redirect, or noindex.
- A cluster in the 0.85–0.95 range contains near-duplicates (product pages differing only
  in color or size). Resolution: make them unique, consolidate them, or canonicalize to
  the reference page.
- Unique pages with small `text` values (word_count) are a separate thin-content finding;
  use `parse` to check their content volume.

## What to Deliver to the User
1. **Duplicate clusters** with similarity scores and URL lists, prioritized by cluster size
   and `min_similarity` (exact duplicates first, then near-duplicates).
2. **Duplicate-content share**: how many pages belong to clusters versus the total.
3. **Pattern-based causes** (when apparent): pagination, catalog filters, UTM duplicates,
   www/http/https duplicates, and utility pages.
4. **Recommendations**: canonical / 301 / noindex / content differentiation, based on the
   cluster type.

## Degradation
No text (an empty list) → `count: 0, clusters: []`; do not crash. Very short texts produce
an unstable simhash, so warn that results for pages with <50 words are approximate. LSH
produces candidates, while the final decision uses the exact Hamming distance, so clusters
will not contain false duplicates (the threshold is checked exactly).

## Integrations
Text sources: `sf-analyzer` (crawl), `parse` (live), `sitemap-crawl` (URL list).
In a full audit, this skill is part of Phase 2 of the `seo-deep-audit` orchestrator
(the "content: uniqueness, near-duplicates" section).
