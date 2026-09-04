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

**Step 1. Collect page text, scoped to the content area.** There are three sources; choose the
one available. Whichever you use, prefer text that already excludes navigation and footer
boilerplate — otherwise shared menus and footers inflate similarity across unrelated pages and
can hide genuine differences:
- **From an SF crawl** (recommended for a large site): take `internal_html.html`
  (or `all_bodytext` from the normalized export) and map each URL to its visible text. This is
  Screaming Frog's own extraction and is not scoped to a content area; a manual boilerplate
  trim before hashing is worth it on templates with heavy menus.
- **From sitemap + parse** (without SF): run `seohead sitemap-crawl --url .../sitemap.xml`,
  then run `seohead parse` on the URL list, collecting each page's `content_text` field (not
  `text` — `text` is the whole document including nav/footer; `content_text` is scoped to the
  resolved content area, nav/footer excluded by default). Or run `seohead markdown-extract` and
  use `content_markdown` when the near-duplicate diff benefits from structure (headings, lists).
- **Prepared list**: ``[{"id": "<url>", "text": "..."}]`` — same rule: feed content-area text,
  not raw page text.

**Step 2. Find duplicate clusters.**
```bash
seohead duplicate-check --input '{"items":[{"id":"https://example.com/a","text":"..."},
  {"id":"https://example.com/b","text":"..."}], "threshold": 0.92}'
```
- `threshold` 0.92 (the default) means nearly identical. Lower it to 0.85 for "highly
  similar" pages, or raise it to 0.97 for "strict duplicates."
- `only_indexable` defaults to true: non-indexable items (canonicalised, noindex) are dropped
  before comparison, since a canonicalised twin is not a defect. Pass `--all-pages` (CLI) or
  `only_indexable: false` (MCP `seo_duplicate_check`) to audit the canonical tags themselves.
- In the response, `exact_duplicates[]` lists groups that hash identically (byte-for-byte same
  extracted text); `clusters[]` lists near-duplicate groups of ≥2 pages, each with pairwise
  similarity and the group's `min_similarity`. A cluster that is fully explained by exact
  duplication is reported once, under `exact_duplicates` only — it never also appears in
  `clusters[]`. `candidate_pairs_checked` is the number of pairs checked exactly (after LSH
  filtering); re-running with a different `threshold` against the same items costs zero requests.

**Step 3. Interpret the results.**
- `exact_duplicates[]` groups (often utility pages or pagination) resolve the same way:
  canonical, redirect, or noindex.
- A `clusters[]` entry with `min_similarity` in the 0.85–0.95 range is a near-duplicate group
  (product pages differing only in color or size). Resolution: make them unique, consolidate
  them, or canonicalize to the reference page.
- Unique pages with a small `content_text`/`word_count` value are a separate thin-content
  finding, already scoped to the content area; use `parse` to check their content volume.

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
