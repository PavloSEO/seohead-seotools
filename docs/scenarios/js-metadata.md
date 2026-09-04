# Scenario 13 — Title, description and H1 that JavaScript writes: two versions of one page

## The question

> Why does the search result show a different title from the one on the page?

Because two documents exist and they disagree. This chain names which of the three headline
fields differ, and whether each is missing from the server response or merely rewritten by it.

## Covers

- **JavaScript** — Page Title Only in Rendered HTML · Page Title Updated by JavaScript · Meta Description Only in Rendered HTML · Meta Description Updated by JavaScript · H1 Only in Rendered HTML · H1 Updated by JavaScript

## The chain

**1. Read the server response on its own terms first.**

```bash
seohead parse --url https://example.com/page
```

`title`, `meta_description` and `headings.h1` here are what a crawler that never executes a
script receives. An empty value is the "only in rendered HTML" case waiting to be confirmed; a
populated one that later differs is the "updated by JavaScript" case.

**2. Compare the two documents.**

```bash
seohead render-check --url https://example.com/page
```

Title, H1 and canonical are compared field by field and any difference is reported — no
materiality threshold, unlike copy and links, because a headline field has no partial version.
The finding quotes both values, so the report says which string each crawler would read rather
than that "the title changes".

**3. Do it in the viewport the template actually branches on.**

```bash
seohead render-check --url https://example.com/page --viewport mobile
```

A responsive template can mount a different component tree at 390px than at 1366px, and a title
or H1 written by that component follows it. Two fixed presets exist rather than free-form
dimensions precisely so two runs can be compared at all.

**4. Take it site-wide only for the templates that differ.**

```bash
seohead crawl-site --url https://example.com --config ./crawl.json --out-dir ./run
```

With `rendering.mode` set to `js`, an escalated page's title, description and H1 are re-read from
the rendered DOM, and the metadata checks — missing, duplicate, too long, templated — run
against that population. `representation` on each page says which document its values came from.

**5. Scan the run before quoting it.**

```bash
seohead log-scan --run ./run
```

## What comes out

`render-check`'s findings name the field and both values:

```json
{
  "js_dependent": true,
  "raw": {"title": "", "h1": ""},
  "rendered": {"title": "Blue Widget 40mm", "h1": "Blue Widget 40mm"},
  "findings": [
    "The title changes after JavaScript: raw '', rendered 'Blue Widget 40mm'; crawlers may index different title values",
    "H1 differs between raw HTML '—' and rendered DOM 'Blue Widget 40mm'"
  ]
}
```

An empty raw title on a product template is a whole-catalogue finding, not a page finding: every
URL that template serves has it.

The meta description is the exception in this group. It is read from the raw response by `parse`
and carried into every crawled page record, but `render-check`'s snapshot pair does not include
it, so a description rewritten by a script is caught by comparing a static crawl against a
rendered one — the same two-crawl diff as [scenario 12](js-directives.md) — rather than by a
single-page report. Saying so is cheaper than a reader trusting a field that was never compared.

## What it costs

One request per `parse`, one request plus one headless render per `render-check`, and one render
per escalated page in the crawl. Nothing is paid. A per-template sample is a handful of renders;
a whole catalogue is a browser launch per URL, which is why escalation exists.

## What it cannot answer

- **Which title Google will display.** Google rewrites titles from page content, headings and
  anchor text regardless of what any document says. This chain reports what each document
  contains, not what will be shown.
- **Whether either version is any good.** Length, uniqueness and templating are checked; whether
  the words earn a click is a person's judgement.
- **A value written after load.** The DOM is captured at the configured milestone — `load` by
  default, because `networkidle` may never arrive on a site with analytics or chat holding
  connections open. A title set two seconds later by a slow request is not in the capture.
- **Anything about a template no sample reached.** Escalation samples URL patterns; the rest of
  the site was measured statically and says so.
