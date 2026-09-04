# Scenario 55 — Comparing two crawls: what changed since the release

## The question

> We shipped a new template on Tuesday. Did it break anything?

## Covers

Nothing in the published catalogue. This is an operating scenario — how to run the
toolkit — rather than a class of site defect.

## The chain

**1. Crawl before the change, and keep the artifacts.**

```bash
seohead crawl-site --url https://example.com --out-dir ./before
```

**2. Crawl again after it, with the same settings.**

```bash
seohead crawl-site --url https://example.com --out-dir ./after
```

The settings matter as much as the timing. A crawl at a different depth, rate, rendering mode
or content-area configuration produces numbers that were not measured the same way. The run
manifest inside each `audit.json` records every results-affecting setting for exactly this
comparison.

**3. Diff them.**

```bash
seohead compare-crawls --before ./old-audit.json --after ./new-audit.json
```

**4. Check both runs before believing the diff.**

```bash
seohead log-scan --run ./run
```

A difference between two runs, one of which contradicts itself, is not a change in the site.

## What comes out

Findings that appeared, findings that disappeared, and pages that changed status — the shape a
release review needs, rather than two full audits to read side by side.

## What it costs

Two crawls. Nothing paid.

## What it cannot answer

- **Why something changed.** The diff is the fact; the cause is in the deploy.
- **Anything about a setting you changed between runs.** Compare like with like or the diff is
  measuring your own configuration.
- **A change on a page neither crawl reached.** Check `run.crawl_partial` on both sides.
