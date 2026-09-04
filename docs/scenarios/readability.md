# Scenario 23 — Readability, spelling and grammar: four columns we read, none we compute

## The question

> Can you check the writing across the site — typos, grammar, and whether it is readable at all?

Yes, with an important caveat stated up front: **this toolkit does not compute any of it.**
Spelling counts, grammar counts and readability scores are columns produced by Screaming Frog's
own analysis. This chain imports them, applies thresholds, groups them by page and turns them
into a backlog. Every number in the output was measured somewhere else.

## Covers

- **Content** — Spelling Errors · Grammar Errors · Readability Difficult · Readability Very Difficult

## The chain

**1. Confirm what a plain crawl can and cannot say.**

```bash
seohead crawl-site --url https://example.com --out-dir ./run --max-urls 200
```

Read `run.checks_skipped` in the resulting `audit.json`. All four checks name themselves absent,
with the reason and the fix in the reason:

```
{"id": "READABILITY_DIFFICULT", "reason": "no Readability/Flesch column"}
{"id": "SPELLING_ERRORS",       "reason": "no Spelling Errors column (enable spell-check in SF)"}
{"id": "GRAMMAR_ERRORS",        "reason": "no Grammar Errors column (enable grammar-check in SF)"}
```

That is the design: a check with no evidence is **named as skipped**, never reported clean. A
zero here would be a lie about the site rather than a fact about the run.

**2. Produce the exports with spell-check and grammar-check enabled in Screaming Frog.** They
are off by default in the crawler's own configuration, so an export made without them yields the
skips above.

**3. Audit the export directory.**

```bash
seohead sf run --exports-dir ./exports --out report --tasks
```

Now `Spelling Errors`, `Grammar Errors`, `Readability` and `Flesch Reading Ease Score` resolve
from `Internal:All`, and four checks activate:

- `SPELLING_ERRORS` — any count above zero, per page, with the count in the finding.
- `GRAMMAR_ERRORS` — the same.
- `READABILITY_DIFFICULT` — a Flesch score below 30, **or** Screaming Frog's own text label
  containing "difficult". That single check answers both "Difficult" and "Very Difficult": the
  label is carried into the finding's details, so a report can distinguish them even though the
  threshold does not.
- `LONG_SENTENCES` — average words per sentence above 25, which is the one language finding here
  with a fix a writer can apply without reading the page.

**4. Turn it into a prioritized backlog.**

```bash
seohead sf tasks --json ./report/audit.json --out ./report
```

**5. Read the flagged pages, not just the counts.**

```bash
seohead markdown-extract --url https://example.com/page
```

A spelling count of 14 on a page whose product names are all trade marks is a dictionary
problem, not a writing problem. Reading one flagged page usually reclassifies a third of them.

## What comes out

The shape of a finding, which carries both the score and the label it was judged against:

```json
{
  "check": "READABILITY_DIFFICULT",
  "target_url": "https://example.com/services/foundation-repair",
  "details": {"flesch": 21.4, "readability": "Very Difficult", "min": 30}
}
```

And a task-list line of the shape `sf tasks` produces, priority and effort already assigned:

```
- [ ] **Spelling errors on the page — 6 pages** `SPELLING_ERRORS` · notice · effort: low
```

## What it costs

Nothing beyond the Screaming Frog crawl you were already making, plus one request per page you
choose to read back. No paid API. Enabling spell-check and grammar-check makes the crawl itself
slower and larger; that cost is Screaming Frog's, not this toolkit's.

## What it cannot answer

- **Whether a flagged word is actually misspelled.** The dictionary is the crawler's, the
  language setting is the crawler's, and product names, place names and technical terms are its
  most common false positives.
- **Whether a readable page is a good page.** Flesch measures sentence and word length. A short,
  simple, wrong sentence scores well.
- **Any of it without an export.** A native crawl has none of these columns and says so; nothing
  in this repository computes readability, spelling or grammar from HTML.
- **What the right reading level is.** A legal notice and a children's page should not score the
  same, and no threshold here knows which page it is looking at.
- **Language quality in text that JavaScript inserts**, unless the crawl that produced the export
  rendered the page.
