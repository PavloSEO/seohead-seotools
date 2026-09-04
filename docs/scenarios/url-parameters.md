# Scenario 48 — Parameters, facets and the crawl budget they eat

## The question

> The crawl never finishes. It keeps finding new URLs on the same three category pages. Why?

A filter interface generates addresses. Colour, size, sort order and page number combine, and a
catalogue of four hundred products becomes an address space with no natural end. Nothing is
broken; the site is simply answering every question it is asked.

## Covers

- **URL** — Parameters · GA Tracking Parameters · Internal Search

## The chain

**1. Crawl with the variant cap set deliberately in the config.** The crawler keeps a bounded
number of distinct query strings per path — `limits.max_query_variants_per_path`, five by
default — so a facet space cannot consume the whole budget before the crawl reaches the pages
that matter.

```bash
seohead crawl-site --url https://example.com --config ./crawl.json --out-dir ./run
```

**2. Scan the run, and read `run.crawl_partial` and the finish reason before anything else.**

```bash
seohead log-scan --run ./run
```

**3. Read the two parameter findings, which are deliberately narrow.**

`URL_HAS_PARAMS` fires on an indexable URL that carries a query string **and has no canonical**.
A parameterized URL that already points a canonical at the clean version is a solved problem and
is not reported, which is why this count is normally far smaller than the number of
parameterized URLs in the crawl.

`URL_TRACKING_PARAMS` fires on an indexable URL carrying `utm_`, `gclid`, `fbclid` and their
relatives. Those belong in inbound campaign links, not in the site's own address space — when
one appears in the crawl, an internal link somewhere was pasted from a campaign builder, and the
site is now competing with a tagged copy of itself.

**4. Check what the site already excludes.**

```bash
seohead robots-check --url https://example.com
```

Read the disallow rules against the facet patterns you just found. This is also where the
opposite error shows up: a broad `Disallow: /*?` written for facets that also blocks
`/blog?page=2`, which is a page the site links to and wants discovered.

**5. Look at one search URL by hand.**

```bash
seohead parse --url https://example.com/search?q=example
```

Internal search results are the one parameterized template that should almost never be
indexable, because it lets anyone generate pages on your domain.

**6. Report it.**

```bash
seohead report-build --audit ./run/audit.json --format csv --out ./parameters.csv
```

## What comes out

A list of parameterized indexable URLs with no canonical, a list of tracking-tagged URLs found
inside the site's own links, and the robots rules that currently apply to them. The remedies are
different for each: a canonical for the facets that are variations of one page, an editorial fix
for the tagged internal links, and a crawl rule only where crawling itself is the cost.

## What it costs

Nothing beyond the crawl and one request per URL inspected by hand. Nothing paid.

## What it cannot answer

- **Whether a parameter creates a distinct page.** `?colour=blue` may be a genuine product
  variant worth indexing or a filter view of the same list. Only somebody who knows the
  catalogue can say.
- **How big the facet space actually is.** The crawler caps variants per path on purpose, so
  the number of parameterized URLs in a run is a floor, not a census.
- **Path-based internal search.** Search routes are recognised through their parameters; a
  route like `/search/blue-shoes` with no query string is not identified as search at all.
- **What Google does with them.** Which parameterized URLs are crawled, and how often, is in
  Search Console, and no crawl of your own site substitutes for it.
- **Whether a tagged URL earns anything.** A `utm_`-tagged URL may be receiving real traffic;
  removing it from internal links is safe, and deleting the URL is not the same decision.
