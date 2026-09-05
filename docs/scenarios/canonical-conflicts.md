# Scenario 10 — Conflicting canonicals: two answers to a question that takes one

## The question

> The theme writes a canonical and the SEO plugin writes another one. Which of them wins, and
> does either of them point somewhere a search engine is allowed to keep?

Two canonical elements on a page is not a preference expressed twice. It is an ambiguity, and
the resolution is the search engine's to make.

## Covers

- **Canonicals** — Multiple Conflicting · Multiple · Non-Indexable Canonical

## The chain

**1. Read the crawl export, because the second element only exists there.**

```bash
seohead sf run --exports-dir ./exports --out report --tasks
```

`CANONICAL_MULTIPLE` fires when Internal:All carries a value in `Canonical Link Element 2`.
A native crawl records the first canonical element and stops, so this is the one canonical
defect that genuinely needs Screaming Frog's own extraction rather than the toolkit's spider.
The same check id covers both published issue names — a page with two identical canonicals and
a page with two contradictory ones are the same markup defect with different luck.

**2. Crawl the site yourself for the other half of the question.**

```bash
seohead crawl-site --url https://example.com --out-dir ./run
```

`CANONICAL_NON_INDEXABLE` needs the canonical *target* to have been fetched, not merely named.
The crawl fetches it, so indexability here is measured — a target that is `noindex`, redirects,
or answers 4xx is a canonical that consolidates a page into nothing.

**3. Check the run before you quote it, and mean it this time.**

```bash
seohead log-scan --run ./run
```

This step exists because of a specific report. `CANONICAL_TO_REDIRECT` — the neighbouring check
in the same family — once fired on **78 live pages whose canonical answered 200**. The crawl
held both slash forms of each URL, `/x` as a 301 and `/x/` as the 200, and the normalised index
that folds a trailing slash away kept only one page per key. Whichever variant was inserted
first became the answer. `CANONICAL_NON_INDEXABLE` was wrong the same way and was fixed in the
same change: both now look at every variant under a key and stay quiet when one of them
contradicts the finding.

The lesson generalises past that bug. A normalised key is right for deciding whether two URLs
are the same page, and wrong for deciding what to fetch or what to name in a finding.

**4. Turn the two lists into one backlog.**

```bash
seohead sf tasks --json report/audit.json
```

## What comes out

Two findings that read very differently to a developer:

```json
{
  "check": "CANONICAL_MULTIPLE",
  "severity": "warning",
  "target_url": "https://example.com/catalog/pump-cdm",
  "message": "Page declares multiple canonical URLs",
  "details": {
    "canonical_1": "https://example.com/catalog/pump-cdm",
    "canonical_2": "https://example.com/catalog/"
  }
}
```

```json
{
  "check": "CANONICAL_NON_INDEXABLE",
  "severity": "warning",
  "target_url": "https://example.com/catalog/pump-cdm-2",
  "message": "Canonical points to a non-indexable URL"
}
```

The first is a template that writes the tag twice. The second is a template that writes it
once, correctly, at a page nobody may index. One is a plugin conflict; the other is an
architecture decision somebody made and forgot.

## What it costs

- One request per crawled page for step 2. Steps 1 and 4 are local file reads.
- Nothing paid. No credentials.
- Screaming Frog is only needed for step 1, and only to have produced the export earlier.

## What it cannot answer

- **Which of the two canonicals is the correct one.** The tool reports that a page declares two
  and prints both. Choosing is a person's job, and usually a template's fault.
- **Why the target is non-indexable.** The finding names the target; whether its `noindex` is
  deliberate is a separate question, and the [noindex audit scenario](noindex-audit.md) is how to ask it.
- **A conflict between an HTML canonical and an HTTP `Link` header.** Only the element is read.
- **Anything on a page the crawl never fetched.** Check `run.crawl_partial` first: a canonical
  target outside the crawl's scope or budget is unjudged, not judged clean.
