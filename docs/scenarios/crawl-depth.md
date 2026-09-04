# Scenario 27 — Crawl depth and dead ends: how far in the site buries its own pages

## The question

> Everything is technically on the site. It just takes six clicks to reach anything worth
> reading. Does that actually matter, and which pages are the worst?

Depth is the cheapest structural measurement there is: the crawl already counted it on the way
in. What it costs is a number nobody argues with, unlike an opinion about navigation.

## Covers

- **Links** — Pages With High Crawl Depth · Pages Without Internal Outlinks · Pages With Uncrawlable Internal Outlinks · Pages With High Internal Outlinks · Pages With High External Outlinks

## The chain

**1. Crawl deeper than you think you need to.**

```json
{"limits": {"max_depth": 8, "max_urls": 2000}}
```

```bash
seohead crawl-site --url https://example.com --config ./crawl.json --out-dir ./run
```

The default depth limit is 5. Crawling to that limit and reporting that nothing is deeper than
5 is a statement about the configuration, not the site. Raise it before asking the question,
and note that both settings are recorded in the run manifest so the number stays comparable.

**2. Read the four counts the audit produces from that one traversal.**

| Finding | Default threshold | What it means |
|---|---|---|
| `DEEP_CRAWL_DEPTH` | more than 4 clicks | the page is buried |
| `NO_INTERNAL_OUTLINKS` | zero | the page is a dead end for the crawler |
| `HIGH_OUTLINKS` | more than 300 internal | a page that links to a large share of the site |
| `HIGH_EXTERNAL_OUTLINKS` | more than 100 external | link focus diluted, or a directory page |

The two outlink counts are disjoint, which sounds obvious and was not: Internal:All's `Outlinks`
column counts internal links only and `External Outlinks` is a separate count, not a subset.
Subtracting one from the other made every page with more external than internal links read as
having no internal links at all.

**3. Look at what the crawl decided not to fetch.**

`discovery.excluded` in the crawl's own result counts every destination the crawl declined,
grouped by reason: outside scope, blocked by `robots.txt`, over the URL-length limit, too many
query variants for one path. That is the honest form of "uncrawlable internal outlinks" this
toolkit currently offers — a census by reason, not an attribution back to the pages that linked
them. Treat it as the reason a depth figure may be lower than the site deserves.

**4. Confirm nothing in the run contradicts itself.**

```bash
seohead log-scan --run ./run
```

**5. Separate depth from reachability before writing the recommendation.**

```bash
seohead crawl-site --url https://example.com --sitemap https://example.com/sitemap.xml --out-dir ./run
```

Depth says a page is far away. Orphan status says nothing links to it at all. They are
different findings with different fixes, and [scenario 3](structure.md) is where the sitemap
reconciliation that produces the second one is described in full.

**6. Hand it over as a table, since the fix is a template change.**

```bash
seohead report-build --audit ./run/audit.json --format xlsx --out ./depth.xlsx
```

## What comes out

```json
{
  "check": "DEEP_CRAWL_DEPTH",
  "severity": "warning",
  "target_url": "https://example.com/catalog/pumps/cdm/cdm-3-11",
  "message": "Page has excessive crawl depth",
  "details": {"crawl_depth": 7, "max": 4}
}
```

The useful deliverable is not this finding. It is the same finding grouped by path prefix: a
depth problem is almost always one template's fault, and 400 product pages at depth 7 is one
missing hub page, not 400 tickets.

## What it costs

- One request per crawled page, at whatever budget step 1 sets. A depth investigation wants a
  larger `max_urls` than a spot check, so this is one of the more expensive chains here.
- Nothing paid.
- Set `speed.min_delay_seconds` for the host before raising the budget, not after.

## What it cannot answer

- **Which pages an uncrawlable link would have led to.** Excluded destinations are counted by
  reason in the run's own excluded map, and not attributed back to the pages that linked them.
  That is a stated partial: the census is real, the per-page attribution does not exist.
- **Whether depth is hurting anything.** Depth correlates with crawl priority; it does not
  measure it. There is no crawl-log or Search Console data in this loop — [scenario
  7](infrastructure.md) is about the server, not about what Googlebot did.
- **Depth through links added by JavaScript.** A menu that hydrates client-side is invisible to
  a raw crawl, and a page it would have reached in two clicks reads as depth 7. See
  [scenario 4](rendering.md).
- **Whether a high-outlink page is wrong.** A sitemap page or a large category index is
  supposed to link to a lot. The threshold is a prompt to look, not a verdict.
- **Depth on a partial crawl.** The deepest page found is bounded by the budget; check
  `run.crawl_partial` and `discovery.max_depth_reached` before quoting a maximum.
