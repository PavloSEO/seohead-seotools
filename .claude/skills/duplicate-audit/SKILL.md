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

## Trigger
- Duplicates are suspected on a large site (pagination, filters, copied content, utility pages).
- "Thin pages" / thin content: you need to find pages with little content or identical pages.
- Search-result cannibalization: find pages competing for the same intent.
- The request is phrased as: "find duplicates," "near duplicate," "duplicate content," "thin
  pages," "thin content," "check uniqueness," "identical pages," "similar pages,"
  "cannibalization," or "catalog duplicates."

## Anti-trigger
- Only one or two specific pages are being compared by eye — a manual diff is faster than standing
  up simhash/LSH for a handful of URLs; use this skill only once the candidate set is large enough
  that pairwise comparison is impractical.
- The concern is a single page being too short/thin with no comparison target — that is a
  `parse`-based word-count check, not a duplicate-clustering problem, though the thin-content note
  in this skill piggybacks on it once clusters already exist.
- The ask is raw HTML/markup diffing (template duplication) rather than content duplication —
  simhash here fingerprints visible body text, not DOM structure.
- No page text can be obtained from any of the three sources (SF crawl, sitemap+parse, prepared
  list) — there is nothing to fingerprint; get text first.

## Preconditions
- [ ] At least one text source is available: an SF crawl export with body text, a fetchable
  sitemap to drive `sitemap-crawl` + `parse`, or a pre-built `[{"id","text"}]` list.
- [ ] A similarity `threshold` decision has been made (0.92 default; lower for "highly similar,"
  higher for "strict duplicates") appropriate to what is being hunted.
- [ ] For a large site (thousands of pages), the SF-crawl or prepared-list path is preferred over
  live `parse` per URL, since the latter issues one request per page.

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

## Decision points
- **`min_similarity = 1.0` vs 0.85–0.95 clusters.** Exact duplicates (utility/pagination pages)
  get canonical/redirect/noindex; near-duplicates (variant product pages) get differentiation or
  consolidation — do not apply the same fix to both cluster types.
- **Choosing the threshold.** The 0.92 default can hide real near-duplicates on templated catalog
  pages or over-flag naturally similar short pages — lower it to 0.85 when hunting broadly, raise
  it to 0.97 only when a strict/exact-duplicate list is explicitly wanted.
- **Short text (<50 words) inside a cluster.** simhash is unstable at that length — treat any
  cluster membership involving such a page as provisional and verify manually rather than reporting
  it with the same confidence as longer-text matches.
- **Unique pages with low word_count.** These are a separate thin-content finding, not a duplicate
  finding — do not fold them into cluster output; flag them alongside with a `parse` content-volume
  check.

## Definition of done
- [ ] Every candidate page supplied has been fingerprinted and is either in a cluster or confirmed
  unique — none silently dropped.
- [ ] Each reported cluster states its `min_similarity` and full URL list, ordered from exact
  (1.0) down to the chosen threshold.
- [ ] Duplicate-content share (clustered pages / total pages) is reported.
- [ ] Any cluster relying on sub-50-word pages is flagged as approximate per the Degradation note.
- [ ] Each cluster/pattern carries a recommendation (canonical/301/noindex/differentiate) matched
  to its cause.

## Cost
`duplicate-check` runs simhash+LSH in one local call with no paid API, so the cost that matters
most is usually the text-collection step, not the clustering call. But "avoids O(N²)" is not
unconditional: LSH buckets by fingerprint, and a templated site's boilerplate can otherwise
dominate every page's fingerprint and defeat the bucketing (a shared 600-token template plus a
30-token unique tail used to put 99.7%+ of a corpus in one LSH bucket at every scale tested).
`find_duplicates` now damps shingles shared by nearly the whole corpus (once it is large enough
for that signal to mean anything — see the module docstring) precisely so this does not happen;
measured on a synthetic templated corpus this took wall-clock time from 4.4s/32.4s/164.6s down to
0.4s/2.2s/8.9s at n=1,000/4,000/10,000, and the false single-cluster collapse (previously nearly
the entire corpus, e.g. 9,994/10,000) dropped to zero clusters when every page's own content is
genuinely distinct. It is still not free at very large scale — n=10,000 remains real, non-trivial
work, not "near-instant" — so budget for it on a crawl in the tens of thousands. If text must be
gathered live via `sitemap-crawl` + `parse`, that is one request per URL (N requests for N pages);
reusing an existing SF crawl export avoids that entirely.

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
produces candidates, and a cluster is complete-linkage: every pairwise similarity inside a
reported cluster — not only the pairs LSH happened to compare — is verified to meet the
threshold, so a cluster never quietly contains a pair below it.

## Integrations
Text sources: `sf-analyzer` (crawl), `parse` (live), `sitemap-crawl` (URL list).
In a full audit, this skill is part of Phase 2 of the `seo-deep-audit` orchestrator
(the "content: uniqueness, near-duplicates" section).
