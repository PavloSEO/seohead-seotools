---
name: backlinks-check
description: >-
  Check backlinks against a provided list of donor pages: whether the target domain
  is linked, what anchor text and rel values the link uses, whether it passes link
  equity (nofollow/ugc/sponsored prevent it), and whether the donor page itself is
  indexable. It answers not only whether a link exists, but WHY it is missing or why
  it does not work. Use when asked to "check my backlinks," "are the links still
  live," "dofollow or nofollow," "is there a link to the site," "check the donor
  pages," or "was the link removed." It does NOT discover someone else's backlink
  profile (that requires Ahrefs/Majestic); it checks a KNOWN list of URLs. Triggers:
  backlinks, links from donor pages, dofollow, nofollow, check links, link removed,
  is the link live, donor page.
---

# Backlinks Check — are links from donor pages live and do they pass link equity?

The presence of an `<a href>` is not enough. A link does not pass link equity if it
uses `rel=nofollow` (or `ugc`/`sponsored`), if the donor page is blocked from indexing
with `meta robots noindex`, if it applies `nofollow` to all links at once, or if it
is canonicalized to another URL. The tool checks all of these conditions and groups
the results by cause.

Important scope boundary: this checks **your list** of donor pages (purchased links,
crowd-marketing links, guest posts, directories); it does not investigate someone
else's backlink profile. External databases (Ahrefs, Majestic, GSC) are not available
here; a request to "show every link to the site" requires one of them.

The tool is `seohead backlinks-check` (CLI + MCP `seo_backlinks_check` + HTTP).

## When to use it
- "check my backlinks," "are the links still live," "was the link removed";
- "dofollow or nofollow," "does it pass link equity";
- "does page X link to our site";
- regular monitoring of purchased backlinks.

## Workflow
**Target: a domain** (any link to the domain or one of its subdomains will match):
```bash
seohead backlinks-check --target example.com --donors "https://donor1.example/post,https://donor2.example/page"
```
**Target: an exact URL** (the address must match exactly):
```bash
seohead backlinks-check --target https://example.com/landing --donors-file donors.txt
```
`--donors-file` is a file containing one URL per line, with `#` marking comments.
`--concurrency N` is the number of parallel requests (default: 3; maximum: 10).
The limit is 500 donor pages per run.

## Response contents
- `summary`: `found` (link exists), `missing` (link is absent), `dofollow`, `nofollow`,
  `on_noindex_page` (the donor page is blocked from indexing, so no equity is passed).
- `results[]` for each donor page: `found`, `status_code`, `donor_indexable`,
  `canonical`/`canonical_elsewhere`, `links[]` (for every link found: `href`, `anchor`,
  `rel`, `follow`, `blocked_by`), and `reason`, which explains why the link is absent
  or why it does not work.

## What to deliver to the user
Provide a table by donor page: donor page → link present → anchor text →
dofollow/nofollow → donor page indexable → conclusion. At the top, provide a summary:
how many links are live, how many pass equity, how many were lost, and for what reason.
Put dead and nofollow links in a separate "requires attention" list.

Combination: **seo-recon** identifies the donor sites (stack, age, hosting), while
**sf-analyzer** checks the user's own site for broken outbound links.
