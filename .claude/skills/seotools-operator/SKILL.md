---
name: seotools-operator
description: >-
  The master skill for running the whole seotools system on a site: crawl it,
  read the audit honestly, run the specialised tools on what the crawl
  surfaced, verify findings live, and produce a deliverable. Use this before
  any other skill in this repository when the ask is "audit this site", "what
  is wrong with this site", "run everything on this site", "stress-test the
  toolkit on a real site", or when you would otherwise write a one-off script
  to check pages. Triggers: audit site, full analysis, crawl and report,
  stress test the toolkit. Localized Russian trigger examples: audit this
  site, full audit, run everything, stress test.
---

# seotools operator — the one loop

## What this repository is for

Checking every page of a site by hand, as an agent, produces the best analysis
and costs the most. A script is cheap and usually stupid. This repository exists
to close that gap: **encode what an agent would do by hand into configs and
scripts, test them on real sites, and get hand-inspection quality at any number
of pages.** The output has to be trusted enough that you use it *instead of*
writing a throwaway script — and if it is not, the fix is a test and an issue,
not a throwaway script.

Everything below was run on 4 260 real URLs across three live sites on the day
it was written. Every command is one that ran; every number is one that came
back.

## Trigger

- "Audit this site", "what's wrong with it", "run everything", "stress-test".
- You are about to write a script that fetches pages and checks something.
- A client asks for a technical SEO deliverable and you have a URL.

## Anti-trigger

- One URL, one question ("is this page indexable?") — use the single tool
  (`parse`, `robots-check`, `render-check`) directly. The loop is for sites.
- The input is a Screaming Frog export — use `sf-analyzer`; this skill's crawl
  step is replaced by the export and the rest applies unchanged.
- You need what actually happens in search (clicks, indexing, field CWV). The
  crawl cannot tell you; see issue #97. Say so rather than inferring it.

## Preconditions

- [ ] `seohead --version` runs from the repository venv
      (`~/Projects/seohead-seotools-public-full/.venv/bin/seohead`).
- [ ] You know whose site it is. Your own: crawl fast. A client's with an
      agreement: the rates below. Anyone else's: do not crawl it.
- [ ] `seohead robots-check --url https://<host>/` read **before** the first
      crawl request — for `crawl_delay` and the sitemap list.
- [ ] A scratch directory for outputs. Never the repository.

## The loop

### 1. Crawl, with a config file, never with flags alone

A config is the record of what was measured. Two real ones:

```json
// own site — fast
{"limits": {"max_urls": 5000, "max_depth": 20, "max_crawl_seconds": 3600},
 "speed":  {"min_delay_seconds": 0.05, "concurrency": 8, "adaptive": true},
 "robots": {"policy": "respect"}, "sitemaps": {"auto_discover": true}}

// client site — 3 URL/s
{"limits": {"max_urls": 5000, "max_depth": 20, "max_crawl_seconds": 5400},
 "speed":  {"min_delay_seconds": 0.333, "concurrency": 3, "adaptive": true},
 "robots": {"policy": "respect"}, "sitemaps": {"auto_discover": true}}
```

```bash
seohead crawl-site --url https://<host>/ --config <cfg>.json --out-dir <scratch>/<host>
```

Validate the rate before spending a request — `effective_request_rate()` in
`seohead.crawl.settings` prints the worst case. `seohead crawl-site --config-help`
lists every setting; the ones marked `*` change **what is found** and are
written into the run manifest, the rest change only cost.

**On speed, learned the hard way:** a WordPress blog crawled at 10 URL/s
started returning 502 after 249 pages and the circuit breaker stopped the
crawl (`finish_reason: errors`). The same URLs, re-fetched one every three
seconds, answered 301 normally — the 502s were caused by the crawl. At 3 URL/s
the same site completed all 3 387 URLs. **The breaker stopping is the tool
working; treat it as a finding about the rate, not the site.**

### 2. Read `audit.json` for honesty before findings

The first four things to read, in this order:

| Field | What it tells you | Today's values |
|---|---|---|
| `run.crawl_finish_reason` | `finished`, or why not | `finished` / `errors` |
| `run.crawl_partial` | did the crawl cover the site | `False` / `True` |
| `summary.check_coverage` | how many of the 113 checks *could* run | `checks_fired: 16, checks_silent: 78` |
| `summary.health_score_basis` | whether the score is comparable to anything | "94 of 113 checks could run; not comparable to a run with full evidence" |
| `summary.totals.pages_by_representation` | static vs rendered — never mix them in one number | `{"static": 3387}` |

A health score with 16 of 113 checks fired is not a health score. Report the
coverage sentence with it, always.

### 3. Look at `by_check` for implausible shares

```python
sorted(summary["by_check"].items(), key=lambda kv: -kv[1])[:10]
```

A check that fired on more than half the pages is almost always wrong — the
tool exists to find the unusual. Today `URL_NOT_IN_SITEMAP` was 392 of 529
findings on a 124-page site: 74% of the report, and every one false (#94).
That share was visible in one line before reading a single URL.

### 4. Verify the serious findings live before reporting them

Every critical you report, you `curl` first. Three seconds apart, a browser
User-Agent, and you record what came back:

```bash
curl -s -o /dev/null -w '%{http_code} -> %{redirect_url}\n' -A 'Mozilla/5.0' https://<url>
```

Today this confirmed a whole `/uslugi/fundament/` section (12 pages) really
returning 404 on a construction company's site — and separately proved that
78 `CANONICAL_TO_REDIRECT` findings were all false, because the canonical
target answered 200 (#95). Same step, opposite outcomes. Both were worth it.

### 5. Run the specialised tools on what the crawl surfaced

The crawl tells you *where* to point them. Each is one command:

| Question the crawl raised | Tool | Real result today |
|---|---|---|
| Does JS change what search sees? | `render-check --url` | "raw and rendered are materially equivalent" on WordPress — so do not render that site |
| Is the structured data a graph or islands? | `schema-check --url` | 2 blocks, 12 entities outside the connected graph, 2 vocabulary errors |
| What is the page *about*, without the template? | `markdown-extract --url` | see the caveat in §7 |
| Is the CSS/JS build sane? | `asset-weight-check --url` | 3 render-blocking in `<head>`, 6 `@font-face` without `font-display` |
| Is there curated context for AI? | `llms-txt-check --url` | present on 2 of 3 sites |
| Which images are heavy, including ones hidden in CSS? | crawl `pages.jsonl` + `parse --options url_sources` | 82 over 300 KB; 4 found only through CSS `url()` |

### 6. Produce the deliverable the finding demands

A finding is not a deliverable. The image case, end to end, as run:

```bash
# 1. crawl already found 82 images > 300 KB in pages.jsonl (size caveat: #99)
# 2. download the heaviest
seohead images-download --urls "<comma list>" --output-dir <scratch>/original
# 3. compress, bounded, format kept
seohead images-optimize --files <scratch>/original --output-dir <scratch>/optimized \
        --max-width 1920 --quality 82 --format keep
#    -> 10 files, 7.92 MB -> 2.58 MB, -67%
# 4. archive for the developer, or upload it yourself
tar -czf images-optimized.tgz <scratch>/optimized
```

That archive is the deliverable. It does not fix a server with no compression
configured — but it proves the server has none, with the bytes to show for it.

### 7. When the tool lies — and it will

Four defects found on three sites in one afternoon, **all in the checks, none
in the traversal**: every URL fetched exactly once, redirects observed not
followed, the breaker held. The conclusions were wrong; the crawl was right.

| # | Symptom you would see | Cause |
|---|---|---|
| #94 | `URL_NOT_IN_SITEMAP` on images and on `wa.me` | compares link destinations, not pages, against the sitemap |
| #95 | `CANONICAL_TO_REDIRECT` on a canonical that answers 200 | crawl holds both slash forms; the normalised index keeps one |
| #96 | 29% of a word count is the template | content area never auto-detected; `<main>`/`<article>` ignored without a selector |
| #99 | an 851 KB WebP reported as 1.5 MB | size measured after decoding the body as text |

The rule that follows: **a finding you cannot reproduce with `curl` is not a
finding.** And when the tool is wrong, the output is an issue with the real
page attached as a fixture — never a local patch, never a throwaway script
that routes around it.

## Decision points

- **Rate.** Own site → fast. Client → 3 URL/s unless the owner sets otherwise,
  and the breaker's verdict overrides the owner's number.
- **Render or not.** Run `render-check` on one page per template first. If raw
  and rendered are equivalent, do not pay for rendering the site.
- **Which findings go in the report.** Critical and warning, each verified
  live. Notices only when a single check is not dominating them.
- **Stop and file.** If `by_check` shows one check above ~50% of findings, stop
  trusting that check for this report, verify five of its hits, file the bug.

## Definition of done

- [ ] `audit.json` exists, `crawl_finish_reason` is `finished` or the reason is
      stated in the deliverable.
- [ ] The coverage sentence (`health_score_basis`) appears next to the score.
- [ ] Every critical in the deliverable was reproduced with `curl`.
- [ ] Any check dominating `by_check` was either verified or filed as a bug.
- [ ] The config file used is attached to the deliverable.
- [ ] The two things the crawl cannot say are said out loud: it measured the
      site as served, not as ranked (#97), and static pages, not rendered ones,
      unless `pages_by_representation` says otherwise.

## Cost

- Network: yes — one request per URL, at the configured rate, same host only.
  External links are recorded and never fetched; a redirect off-host is
  recorded and never followed.
- Money: none. Every tool here is free; the paid sources are gated behind
  `sources-doctor` and a spend log and are not part of this loop.
- Time: 387 pages at 20 req/s worst case took under a minute; 3 387 pages at
  3 req/s took about twenty. Rendering is an order of magnitude more per page.
- Writes: only under `--out-dir` and the scratch directory you chose.
