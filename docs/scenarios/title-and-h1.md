# Scenario 18 — Title and H1: two fields, one CMS field behind them

## The question

> Every page's H1 is identical to its title. Is that a problem, or is that just how our theme
> works?

Both, usually. A theme that prints one CMS field into `<title>` and `<h1>` produces a site where
the two never diverge, which is a template decision with site-wide consequences — and it shows
up as four different findings that all trace back to one include.

## Covers

- **Page Titles** — Same as H1
- **H1** — Missing · Multiple · Duplicate · Over 70 Characters

## The chain

**1. Crawl once.** The record keeps `title`, `h1` and a second `h1_2` slot side by side, which is
what makes the comparison possible without a second fetch.

```bash
seohead crawl-site --url https://example.com --out-dir ./run --max-urls 200
```

**2. Scan the run.**

```bash
seohead log-scan --run ./run
```

**3. Read the four findings as one story.** They come out of a single pass over the indexable
HTML pages:

- `TITLE_EQUALS_H1` — the two strings match after trimming. On a themed site this fires on
  nearly every page, and a check that fires on more than half the pages is telling you about the
  template, not about the pages.
- `H1_MISSING` — no H1 at all, which on a hero-image layout usually means the heading is inside
  the image.
- `H1_MULTIPLE` — a second H1 was recorded; the finding carries **both texts**, not just a count,
  so the report says which heading to demote.
- `H1_DUPLICATE` — the same H1 text on several pages, emitted as a group keyed by that text.
- `H1_TOO_LONG` — over 70 characters by default.

**4. Confirm the template theory on one page.**

```bash
seohead parse --url https://example.com/page
```

`parse` returns `headings` with every level's text, so you can see whether the H1 and the title
really are the same string or merely start the same way.

**5. Turn it into one task rather than four hundred.**

```bash
seohead report-build --audit ./run/audit.json --format docx --out ./headings-task.docx
```

## What comes out

The shape of an `H1_MULTIPLE` finding, with the evidence needed to act on it:

```json
{
  "check": "H1_MULTIPLE",
  "target_url": "https://example.com/page-a",
  "details": {"h1_count": 2, "h1_texts": ["Foundation repair", "Get a quote"]}
}
```

And, from the example audit's own backlog, what that becomes:

```
- [ ] **Multiple H1 elements on one page — 1 page** `H1_MULTIPLE` · warning · effort: medium
    - _How to fix:_ Keep one H1 and change the remaining top-level headings to H2 or H3.
```

When `TITLE_EQUALS_H1` covers the whole site, the deliverable is one line about the theme, not a
row per URL. When it covers eleven pages, those eleven were edited by hand and are worth reading.

## What it costs

One request per crawled page, plus one live confirmation. No paid API, no rendering.

## What it cannot answer

- **Whether title and H1 *should* differ.** On a small single-purpose page they legitimately say
  the same thing. This chain reports the fact; the judgement is editorial.
- **An H1 whose only text is an image's alt attribute.** That is not detected: the heading reads
  as empty and is reported as missing.
- **Where the H1 sits on the page.** Order and nesting are a separate chain —
  see the [heading hierarchy scenario](heading-hierarchy.md).
- **Headings written by JavaScript.** The crawl reads served HTML; see the [rendering scenario](rendering.md)
  before concluding a page has no H1.
- **Whether the H1 targets the right thing.** No demand or ranking data is in this loop.
