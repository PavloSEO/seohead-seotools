# Scenario 21 — Thin content: what "thin" means once the template stops counting

## The question

> The last audit said 180 pages are thin. Our pages have 600 words each. Which of us is wrong?

Probably neither. A 600-word page whose navigation, sidebar and footer contribute 450 of those
words has 150 words of its own. The disagreement is about which words are being counted.

## Covers

- **Content** — Low Content Pages

## The chain

**1. Crawl, with the content region resolved per page.**

```bash
seohead crawl-site --url https://example.com --out-dir ./run --max-urls 200
```

The region is detected from the document's own semantics: `<main>`, then `[role="main"]`, then
`<article>`, and the strategy that matched is recorded per page as `auto_main`, `auto_role_main`,
`auto_article` or `default_body`. That last value is the warning sign — it means nothing semantic
matched and the count includes whatever the fallback could not strip.

The default before this existed counted 126 template words out of 433 on a live WordPress post.
That 29% inflation pushes every page of a template in the same direction, which is why a
site-wide thin-content count computed from whole-body text is unusable rather than merely noisy.

**2. Scan the run.**

```bash
seohead log-scan --run ./run
```

One of its rules is words counted on a zero-byte page. Another is a text ratio above 100%. Both
are thin-content arithmetic that cannot be true.

**3. Read the two checks separately.** `THIN_CONTENT` fires below 200 words of content-region
text. `LOW_TEXT_RATIO` fires below 10% text against the HTML byte count. They disagree usefully:
a page with 400 words inside 900 KB of markup is not thin, it is buried.

**4. Confirm on one page, and see the arithmetic.**

```bash
seohead markdown-extract --url https://example.com/page
```

Two renderings come back — `content_markdown` and `full_markdown`. The difference between their
word counts is the boilerplate, stated rather than assumed.

**5. Override the region where the markup is not semantic.**

```bash
seohead markdown-extract --input '{"url": "https://example.com/page", "content_area": {"include_selector": "#content"}}'
```

A selector that matches nothing reports `fallback_default_body` rather than quietly detecting
something else. A wrong selector should be visible.

**6. Build the writer's list.**

```bash
seohead report-build --audit ./run/audit.json --format xlsx --out ./thin.xlsx
```

## What comes out

The finding carries the threshold it was judged against, so the number is reproducible:

```json
{
  "check": "THIN_CONTENT",
  "target_url": "https://example.com/page-b",
  "details": {"word_count": 50, "threshold": 200}
}
```

And the extraction that explains it:

```
strategy: auto_main
content:  429 words
full:     1104 words
```

Any threshold applied to the larger number is measuring the template.

## What it costs

One request per crawled page, one per page re-read with `markdown-extract`. Local parsing.
Nothing paid.

## What it cannot answer

- **Whether a short page is a bad page.** A contact page with 40 words is correct. Thin is a
  measurement; "should be longer" is an editorial claim this cannot make.
- **What a reader considers the content.** A page whose sidebar carries the real answer is
  extracted as if the sidebar were furniture. Override the selector when that is true.
- **Content assembled by JavaScript.** An app shell reads as thin whatever it later renders.
  See the [rendering scenario](rendering.md).
- **Whether the page has enough of the *right* words.** Relevance needs a query or a topic model
  to be relevant to, and neither is in this loop.
- **Whether thin pages are costing anything.** No traffic or index-coverage data is here.
