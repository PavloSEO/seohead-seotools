# Scenario 37 — Directives under rendering: a noindex only one copy of the page carries

## The question

> A developer swears the page is indexable. Search Console disagrees. Who is reading which copy
> of the page?

An indexing directive is the one thing on a page that must not depend on whether a script ran.
This chain finds the pages where it does, in either direction.

## Covers

- **JavaScript** — Noindex Only in Original HTML · Nofollow Only in Original HTML

## The chain

**1. Read the directive the server actually sent.**

```bash
seohead parse --url https://example.com/page
```

`robots` and `robots_meta` come from the response body, before any script ran. Every
crawler-addressed robots tag is kept rather than merged into one: a page can be `noindex` for one
user agent and open to the rest, and flattening that loses the finding.

**2. Establish whether the rendered document is a different document at all.**

```bash
seohead render-check --url https://example.com/page
```

If raw and rendered are materially equivalent, the question is closed — there is one document and
`parse` already read it. If they are not, keep going.

**3. Crawl the site statically, and keep the audit.** This is the directive as every
non-rendering crawler receives it:

```bash
seohead crawl-site --url https://example.com --out-dir ./run
```

**4. Crawl it again with rendering escalated.** A page re-fetched through the browser has its
`meta_robots` re-read from the rendered DOM, so the same check id now describes the
post-JavaScript document:

```bash
seohead crawl-site --url https://example.com --config ./crawl.json --out-dir ./run
```

`crawl.json` sets `rendering.mode` to `js`; the [rendering scenario](rendering.md) has the escalation block
that keeps a second crawl affordable.

**5. Diff the two audits.**

```bash
seohead compare-crawls --before ./old-audit.json --after ./new-audit.json
```

A `NOINDEX` or `NOFOLLOW_PAGE` in `left` — present before, absent after, the URL crawled both
times — is a directive that exists only in the original HTML. The same check in `entered` is
the mirror image: a directive a script adds, which is the worse of the two, because the copy
most crawlers read looks clean.

**6. Confirm neither run contradicts itself.**

```bash
seohead log-scan --run ./run
```

## What comes out

The diff, read as a statement about directives rather than about fixes:

```json
{
  "summary": {"entered": 0, "left": 1, "appeared": 0, "disappeared": 0},
  "left": [{"check": "NOINDEX", "target_url": "https://example.com/page"}]
}
```

Nothing was fixed. One URL was measured two ways and its directive did not survive the change of
method. That is why `compare-crawls` keeps `left` (still crawled, no longer matching) apart from
`disappeared` (not in this crawl at all) instead of merging both into "gone".

## What it costs

Two crawls of the same site, the second paying for a headless render on each escalated page. Run
them back to back with the same budget, rate and scope, or the diff is measuring your own
configuration. The run manifest inside each `audit.json` records every results-affecting setting
so that this is checkable rather than remembered.

## What it cannot answer

- **Which document Google used.** Google renders, eventually and not always. A directive that
  differs between the two documents is a defect whichever copy wins on a given day, and that is
  the strongest claim available here.
- **An `X-Robots-Tag` that varies by user agent.** The header is read as served to this client; a
  server that answers differently for Googlebot is invisible to a single fetch.
- **A directive changed by an interaction.** Only page load is observed — nothing is clicked,
  scrolled or submitted.
- **Whether the page is indexed.** Indexability is not indexation, and there is no Search Console
  data anywhere in this loop.
