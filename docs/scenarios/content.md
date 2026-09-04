# Scenario 6 — Content extraction: how much of this page is actually the page

## The question

> The audit says these pages are fine. Read one and tell me what it really says.

## The chain

**1. Extract the content region as Markdown.**

```bash
seohead markdown-extract --url https://example.com/page
```

Two renderings come back: `content_markdown` (the content region only) and `full_markdown`
(everything, header and footer included). The difference between them *is* the boilerplate.

The region is detected from the document's own semantics — `<main>`, then `[role="main"]`,
then `<article>` — and the strategy used is reported per page as `auto_main`, `auto_role_main`,
`auto_article` or `default_body`. On a live WordPress post, the whole-body default counted 433
words where `<main>` holds 429: 126 of them template, including a skip-to-content link and the
literal word "header".

**2. Override it when a site's markup is not semantic.**

```bash
seohead markdown-extract --input '{"url": "https://example.com/page", "content_area": {"include_selector": "#content"}}'
```

Configuration wins over detection. A selector that matches nothing reports
`fallback_default_body` rather than quietly detecting something else — a wrong selector should
be visible, not smoothed over.

**3. Find where the template drifts across pages.**

```bash
seohead boilerplate-report --input '{"pages": [{"url": "https://example.com/a", "boilerplate_hash": "aaa"}, {"url": "https://example.com/b", "boilerplate_hash": "bbb"}]}'
```

Hashing header and footer per page finds the pages whose template differs from every other —
usually a legacy section nobody remembers, sometimes a broken include.

## What comes out

```
strategy: auto_main
content:  429 words
full:     1104 words
```

Two-thirds of that page is navigation and footer. Any threshold applied to the larger number
is measuring the template.

## What it costs

One request per page. Local parsing. Nothing paid.

## What it cannot answer

- **Whether the content is good.** Extraction is not judgement.
- **What a *reader* considers the content.** A page whose sidebar carries the real answer will
  be extracted as if the sidebar were furniture. Override the selector when that is the case.
- **Content assembled by JavaScript.** See [scenario 4](rendering.md).
