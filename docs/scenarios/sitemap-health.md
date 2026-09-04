# Scenario 30 — Sitemap health: the entries that should not be in it

## The question

> Search Console says our sitemap has errors, but it does not say which URLs. Can you tell me
> what is in there that should not be?

A sitemap is a recommendation, and the only way to make a recommendation worthless is to fill
it with URLs that redirect, 404, carry a `noindex`, or point somewhere other than their own
canonical. Every one of those tells a crawler that the list is not maintained.

## Covers

- **Sitemaps** — Non-Indexable URLs In Sitemap

## The chain

**1. Expand the sitemap, including any index files.**

```bash
seohead sitemap-crawl --url https://example.com/sitemap.xml
```

The result carries `count` and, per entry, the raw `loc`, a normalized form and `lastmod`. Read
`count` first: a sitemap that declares far fewer URLs than the site has pages is a different
problem from one that declares too many.

**2. Confirm the site actually points at the sitemap you just read.**

```bash
seohead robots-check --url https://example.com
```

The `sitemaps` array is what `robots.txt` declares. A sitemap that is generated but never
declared, or an old path still declared after a migration, both show up as a mismatch here.

**3. Crawl, seeded from the sitemap, so every declared URL is fetched and judged.**

```bash
seohead crawl-site --url https://example.com --sitemap https://example.com/sitemap.xml --out-dir ./run
```

**4. Scan the run.**

```bash
seohead log-scan --run ./run
```

**5. Read `SITEMAP_URL_NON_INDEXABLE`.** One finding per declared URL that cannot be indexed as
declared, which in practice is four different mistakes wearing the same label:

| What the URL does | Where the fix belongs |
|---|---|
| returns 3xx | the generator: declare the destination |
| returns 4xx or 5xx | the generator, or the page |
| carries `noindex` | one of the two is wrong; decide which |
| canonicalises elsewhere | declare the canonical instead |

**6. Walk one of the redirecting entries to see where it now lands.**

```bash
seohead redirects-check --url https://example.com/old
```

**7. Export the list.**

```bash
seohead report-build --audit ./run/audit.json --format csv --out ./sitemap-health.csv
```

## What comes out

A per-URL list with the reason each entry does not belong, which is what makes it actionable:
"non-indexable URLs in sitemap: 61" is a number, and "these 61 URLs redirect, and here is where
each one goes" is a regeneration rule.

The common cause is worth naming: the generator emits the URL the CMS stores, while the site
serves a normalized form of it. Every entry then redirects, and the sitemap becomes a list of
addresses the site itself has stopped using.

## What it costs

One request for the sitemap plus its children, and one per declared URL during the crawl.
Nothing paid.

## What it cannot answer

- **The protocol limits.** Neither the 50,000-URL ceiling nor the 50 MB file-size ceiling is
  asserted, so a sitemap that exceeds either is not reported as invalid here.
- **Which sitemap a URL came from.** URLs appearing in more than one child sitemap are counted,
  not named individually.
- **Whether `lastmod` is true.** The date is read as declared. A generator that stamps today on
  every entry produces a valid sitemap that means nothing, and nothing here detects that.
- **Whether Google fetched it.** Submission, fetch status and the errors Search Console counts
  are on Google's side of the fence.
- **Whether a missing page should be in it.** This chain judges the entries that exist — the
  other direction is [sitemap reconciliation](sitemap-reconciliation.md).
