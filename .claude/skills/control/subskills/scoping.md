# Scoping: what this site is, before deciding what to run

Five minutes of reconnaissance decides an hour of crawling. The goal is not to audit anything
yet — it is to know what would be wasted.

## What to establish

| Question | How | What it changes |
|---|---|---|
| How many URLs? | `sitemap-crawl --url .../sitemap.xml` | the budget, the rate, whether rendering is affordable |
| What is it built on? | `tech-detect --url` | whether JS rendering is likely to matter at all |
| What kind of site? | read the home page | which method skills are relevant |
| What does robots allow? | `robots-check --url` | whether a whole section is invisible to the crawl |
| Is there a second hostname? | `mirror-check` | a duplicate-content problem invisible to a single-host crawl |

The `audit-roadmap` skill turns this into a written plan when the site is large enough to need
one.

## What to skip, and say you skipped

- **Rendering**, when `render-check` on one page per template shows raw and rendered are
  equivalent. Most WordPress sites are.
- **Regional structure**, when there are no city subdomains or directories.
- **Backlink verification**, without a donor list — nothing here discovers someone else's
  backlink profile.
- **Paid sources**, unless somebody has agreed to the spend.

Skipping is a decision; it belongs in the deliverable. A section absent because it was
irrelevant reads exactly like a section absent because it was forgotten.

## Budget arithmetic

At 3 URL/s: 1000 URLs ≈ 6 minutes, 5000 ≈ 28 minutes, 20000 ≈ 2 hours. Rendering multiplies the
per-page cost by roughly an order of magnitude, which is why escalation samples URL patterns
rather than rendering everything.

Set `limits.max_urls`, `limits.max_depth` and `limits.max_crawl_seconds` deliberately. A crawl
with no budget at all runs forever on an infinite URL space — a faceted catalogue is exactly
that — and the config refuses one.
