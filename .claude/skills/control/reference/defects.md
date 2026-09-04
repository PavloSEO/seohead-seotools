# Defects found on live sites, and what gave each one away

Not a changelog. A pattern list: every one of these was recognisable from the report before
anybody opened the code, and the same shapes will give away the next ones.

| # | Symptom in the report | Cause | Now caught by |
|---|---|---|---|
| #94 | `URL_NOT_IN_SITEMAP` on images and on `wa.me` — 392 findings on 124 pages | compared link destinations against the sitemap instead of pages | `log-scan`, chain tests |
| #95 | `CANONICAL_TO_REDIRECT` on a canonical that answers 200 — 78 of them | crawl holds both slash forms; a many-to-one key used as a one-to-one index | `log-scan`, chain tests |
| #96 | 29% of a word count is the template | content area never auto-detected; `<main>` ignored without a selector | chain tests |
| #99 | an 851 KB WebP reported as 1.5 MB | size measured after decoding the body as text | `log-scan`, chain tests |
| #115 | a 42% redirect rate that was the crawler's own doing | the sitemap seeder normalised the trailing slash away before fetching | chain tests (xfail until fixed) |

## The four shapes

**1. A count larger than its own population.** More findings of one check than there are pages
to have them. Visible in one line of `by_check`.

**2. A size that disagrees with the file.** Anything measured after a transformation rather
than before it. Download one file and compare.

**3. A claim about a URL that was never fetched.** Cross-check the finding's target against
`pages.jsonl`.

**4. A number that changed meaning between stages.** Both stages correct alone; the handoff
wrong. This is the hardest to see and the reason `tests/chains/` exists.

## What they had in common

All five are in the **checks**, none in the traversal. Every URL was fetched exactly once,
redirects were observed and not followed, off-host links were recorded and never requested, the
circuit breaker held. The crawl was right; the conclusions drawn from it were not.

That is worth knowing when triaging: doubt the interpretation before doubting the fetch.

## The rule

When the tool is wrong, the output is an issue with the real page attached as a fixture. Not a
local patch. Not a throwaway script that routes around it. The next person to run it has to
inherit the fix, not the workaround.
