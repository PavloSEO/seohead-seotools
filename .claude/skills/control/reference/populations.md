# Which set each check describes, and what it must never be compared to

Most wrong findings are a comparison between two sets that describe different things. The sets
below look interchangeable and are not.

| Set | What is in it | What it is not |
|---|---|---|
| **fetched pages** | every URL the crawl requested and got an answer for | not every URL it *saw* |
| **link destinations** | every `href` recorded, including images, off-host and never-fetched | not pages |
| **HTML pages** | fetched, 2xx, HTML by its own `Content-Type` | not assets, not redirects |
| **indexable pages** | HTML pages, same host, not `noindex` by meta or `X-Robots-Tag` | not "everything that answered 200" |
| **sitemap-declared** | the `loc` values a sitemap published | not necessarily crawled, or even reachable |
| **reachable** | destinations of at least one recorded hyperlink | not "fetched": a seeded URL is fetched without being linked |

## The comparisons that are valid

- **"missing from the sitemap"** — *indexable pages* minus *sitemap-declared*. Comparing link
  destinations here reports images, `wa.me` links and URLs never fetched, which was 74% of one
  live report (#94).
- **"orphan"** — *sitemap-declared* minus *reachable*. Note the second set is **reachable**, not
  indexable: narrowing it invents an orphan for every `noindex` URL a sitemap legitimately
  declares.
- **"broken link"** — *link destinations* with a 4xx, which is the one place link destinations
  are the right population.
- **any per-page check** — *HTML pages*. A count above that population is arithmetic, not a
  finding.

## Withheld rather than guessed

On a partial crawl, "nothing links here" is unprovable. `ORPHAN_PAGE`, `SITEMAP_ORPHAN` and the
unlinked-* checks are therefore **withheld and named as skipped** when the aggregator marks a
crawl partial, rather than reported from incomplete evidence. Check `run.crawl_partial` before
reading any absence as a fact.

## A normalised key is not a URL

`norm_url` folds a trailing slash away so a canonical written without one matches the page that
has it. That tolerance is right for **comparison** and wrong for everything else: use it to
decide whether two URLs are the same page, never to decide what to fetch (#115) and never to
name a URL in a finding — a reader has to be able to look the address up.
