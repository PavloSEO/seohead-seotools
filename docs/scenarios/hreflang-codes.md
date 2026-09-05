# Scenario 32 — Hreflang codes and x-default: the annotation that is only nearly right

## The question

> Our developer says the hreflang tags are done. They look done. Why is the UK site still
> being shown in the United States?

Because `en-UK` is not a country code. The ISO 3166-1 code for the United Kingdom is `GB`, an
invalid annotation is ignored in full rather than in part, and a set with no fallback has
nothing to offer a visitor who matches none of it.

## Covers

- **Hreflang** — Incorrect Language & Region Codes · Multiple Entries · Missing Self Reference · Missing X-Default · Not Using Canonical · Outside <head>

## The chain

**1. Validate one page's set against the actual standards.**

```bash
seohead hreflang-check --url https://example.com/page
```

The validator checks each value as an ISO 639-1 language optionally followed by an ISO 3166-1
alpha-2 or UN M.49 region, folds case before comparing (`en-US` and `en-us` are one annotation
declared twice, not two annotations), and reports the absence of `x-default` and the absence of
a self-reference as issues in their own right.

**2. Do the same for a set of pages without crawling the whole site.**

```bash
seohead parse --urls https://example.com/page,https://example.com/
```

Useful when a client has named the five templates they care about and a full crawl is not yet
authorised.

**3. Run the audit over the annotation graph for the site-wide answer.**

```bash
seohead sf run --exports-dir ./exports --out report --tasks
```

Five checks group by the declaring page, which is how a crawler reads one page's set:

| Finding | The rule it enforces |
|---|---|
| `HREFLANG_INVALID_CODE` | a valid language, optionally a valid region — `en-GB`, not `en-UK` |
| `HREFLANG_MULTIPLE_ENTRIES` | each language/region combination declared exactly once |
| `HREFLANG_MISSING_SELF_REFERENCE` | every page in a set names its own URL and language |
| `HREFLANG_MISSING_XDEFAULT` | a fallback for visitors who match no declared alternate |
| `HREFLANG_NOT_CANONICAL` | annotations point at each target's canonical, not a duplicate |

`HREFLANG_MISSING_XDEFAULT` is the only notice among them. The other four are warnings because
each one makes an annotation ambiguous or invalid; a missing `x-default` merely leaves the
fallback unstated.

**4. Add `HREFLANG_OUTSIDE_HEAD` from a native crawl, since the export above cannot carry it.**

```bash
seohead crawl-site --url https://example.com --out-dir ./run
```

A browser closes `<head>` at the first element that does not belong there, and an alternate
link after that point is read from `<body>` instead — every other check in this scenario would
judge it as if it still counted. That is the parser's own answer to where the tag ended up, not
a reading of the source text, so it exists only where this crawl's own parse tree was built.

**5. Check the run, then export.**

```bash
seohead log-scan --run ./run
```

```bash
seohead report-build --audit ./run/audit.json --format md --out ./hreflang-codes.md
```

## What comes out

From step 1, the single-page form, which is the one to paste into a ticket:

```json
{
  "ok": true,
  "count": 3,
  "alternates": [
    {"hreflang": "en-UK", "href": "https://example.com/en/"},
    {"hreflang": "de", "href": "https://example.com/de/"},
    {"hreflang": "de", "href": "https://example.com/de-at/"}
  ],
  "issues": [
    "malformed hreflang code: 'en-UK' ('UK' is not an ISO 3166-1 alpha-2 or UN M.49 region code)",
    "duplicate hreflang: de",
    "no x-default alternate",
    "page does not self-reference in its hreflang set"
  ]
}
```

Four problems in three lines of markup, all of them mechanical, none of them visible to a
person reading the page.

## What it costs

- One request per URL in steps 1 and 2, plus the crawl in step 4. Steps 3 and 5 are local reads.
- Nothing paid.
- This is the cheapest chain in this directory: a single-page validation costs one GET.

## What it cannot answer

- **Whether the language of the page matches its own annotation.** A page declaring
  `hreflang="fr"` while serving English is structurally perfect and substantively wrong. No
  language detection runs here.
- **Whether a region should exist at all.** `es-MX` is valid whether or not the business sells
  in Mexico.
- **Whether the annotation is inside `<head>`, on a plain Screaming Frog export.**
  `HREFLANG_OUTSIDE_HEAD` needs the parse tree a native crawl builds; an export-only run names
  it skipped rather than reporting it clean.
- **Whether the other end agrees.** Reciprocity, return links and target status are
  the [hreflang return links scenario](hreflang-return-links.md).
- **Annotations delivered in an XML sitemap or an HTTP header.** Only the HTML `link` elements
  are read.
