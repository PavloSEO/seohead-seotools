# Scenario 2 — Metadata and thin pages: which pages actually need writing

## The question

> We have 400 pages and a writer for two weeks. Which pages are worth their time?

## The chain

**1. One crawl, everything downstream reads it.**

```bash
seohead crawl-site --url https://example.com --out-dir ./run --max-urls 200
```

**2. Read the audit honestly.** `audit.json` holds three things that are easy to confuse:

- `summary.by_check` — what fired
- `run.checks_skipped` — what could not run, and why
- `summary.check_coverage` / `health_score_basis` — how much of the registry actually ran

A health score computed from a third of the checks is not a score. The audit says so rather
than quietly averaging what it happened to have.

**3. Find the pages that are thin, not just short.**

```bash
seohead duplicate-check --input '{"items": [{"url": "https://example.com/a", "text": "one paragraph of body copy"}, {"url": "https://example.com/b", "text": "one paragraph of body copy"}]}'
```

Word count alone lies on a template-heavy site: a 40-word product page reads as substantial
when the mega-menu lends it 600 words. The crawl scopes text to the page's real content region
(`<main>`, `[role="main"]`, then `<article>`) and records which one it used, so a thin page is
thin by its own content rather than by its navigation.

**4. Check the metadata that is missing or duplicated.**

```bash
seohead parse --url https://example.com/page
```

One page at a time when you want to see everything about it: title, description, headings,
canonical, robots directives, Open Graph, JSON-LD, and the content-area strategy that produced
the word count.

**5. Build the backlog.**

```bash
seohead report-build --audit ./run/audit.json --format xlsx --out ./backlog.xlsx
```

## What comes out

A spreadsheet whose rows are ordered by severity, each naming the page, the check, and what to
do. The rows that matter for a writer are `THIN_CONTENT`, `TITLE_MISSING`, `TITLE_DUPLICATE`,
`DESC_MISSING`, `DESC_DUPLICATE` and `H1_MISSING`.

```
| severity | check           | url                        | what to do                    |
| warning  | THIN_CONTENT    | /services/foundation       | 121 words of real content     |
| warning  | DESC_DUPLICATE  | /services/{9 pages}        | one description, nine pages   |
```

## What it costs

One request per page. Nothing paid. The whole chain on a 400-page site is a single crawl plus
local analysis.

## What it cannot answer

- **Whether the text is any good.** Every check here is structural. "This page has 800 words"
  and "this page is worth reading" are different claims, and only one of them is measurable.
- **What the page should rank for.** Demand data is a separate, partly paid chain
  (`keywords-expand`, `keywords-exact`, `serp-fetch`) and needs credentials.
- **Whether duplicate descriptions are deliberate.** Nine identical descriptions across nine
  regional pages may be a template bug or a decision. The tool reports the fact.
- **Anything about pages the crawl did not reach.** Check `run.crawl_partial` before reading a
  count as "the site".
