# Scenario 16 — The noindex audit: proving a migration did not take the site offline

## The question

> We cut over to the new CMS on Saturday. Staging was noindexed for months. How do I prove, on
> Sunday morning, that production is not?

This is the one check nobody wants to run from memory. A `noindex` that ships with a template
is invisible to every person looking at the site, costs nothing to detect, and is the single
most expensive mistake a migration can make.

## Covers

- **Directives** — Noindex · None · Nofollow

## The chain

**1. Crawl the old site while it still exists, and keep the artifacts.**

```bash
seohead crawl-site --url https://example.com --out-dir ./before
```

This is the step people skip and then cannot recover. After the cutover there is no way to
reconstruct what the previous templates declared.

**2. Crawl the new one with the same settings.**

```bash
seohead crawl-site --url https://example.com --out-dir ./after
```

Same rate, same depth, same rendering mode. The run manifest inside each `audit.json` records
every results-affecting setting so that this comparison is between two sites and not between
two configurations.

**3. Diff them, and read the `NOINDEX` line first.**

```bash
seohead compare-crawls --before ./old-audit.json --after ./new-audit.json
```

Findings that appeared, findings that disappeared, pages that changed status. A `NOINDEX` count
that went from 3 to 340 is the whole answer, and it is one line.

**4. Read `none` as the two directives it is.**

A template that emits `<meta name="robots" content="none">` raises both `NOINDEX` and
`NOFOLLOW_PAGE`, because the directive is shorthand for exactly that pair. Sites migrating
between CMSes hit this more than they expect: `none` is an easy default in a template variable
that was meant to be empty, and a substring search for "noindex" will never find it.

**5. Check the crawl of the new site is not lying about its own coverage.**

```bash
seohead log-scan --run ./run
```

An `after` crawl that stopped early has a low `NOINDEX` count for a reason that has nothing to
do with the templates. `run.crawl_partial` decides whether step 3's diff is a fact.

**6. Prove the negative for the staging host too, if it is still reachable.**

```bash
seohead crawl-site --url https://example.com --robots report_only --out-dir ./run
```

`report_only` fetches `robots.txt`, reports everything it would block, and crawls anyway. On a
staging host that disallows everything, this is the difference between "we could not check" and
"we checked, and here is what is inside".

## What comes out

The single number the release needs, from `summary.by_check` on each side:

```json
{
  "before": {"NOINDEX": 3},
  "after":  {"NOINDEX": 340, "NOFOLLOW_PAGE": 340}
}
```

Two identical counts on the second line are the fingerprint of `none` rather than of two
separate mistakes.

## What it costs

- Two crawls of the same site, one of them ideally before the release.
- Nothing paid.
- The `report_only` run in step 6 is a deliberate impoliteness: use it on hosts you own.

## What it cannot answer

- **Whether the pages were deindexed.** Removal from an index takes time and is visible only in
  Search Console. This chain measures what the site says, on the day it says it.
- **Whether a `noindex` is correct.** Filters, internal search results and thank-you pages
  should carry one. The count going up is not automatically a defect; the count going up by the
  size of a template is.
- **Why it changed.** The diff is the fact; the cause is in the deploy.
- **A directive present only after JavaScript runs.** See [scenario 4](rendering.md).
- **Anything under a path neither crawl reached.** Compare `run.crawl_partial` on both sides
  before reading a disappearance as a fix.
