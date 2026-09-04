# Scenario 35 — Rendering: does a crawler see what a visitor sees

## The question

> The page looks fine in my browser. Why does the audit say it has no content?

## Covers

- **JavaScript** — Contains JavaScript Content · Contains JavaScript Links · Pages with Blocked Resources

## The chain

**1. Compare raw HTML against the rendered DOM for one page.**

```bash
seohead render-check --url https://example.com/page --viewport desktop --wait load
```

This is the diagnosis, and it is one request plus one browser render. It reports what exists
only after JavaScript: text, internal links, title, canonical, `h1`, and Schema.org — plus lab
timings (TTFB, FCP, LCP, CLS).

**2. If the crawl itself needs rendering, it says so before scoring anything.** A crawl whose
start page has zero internal links, or an empty SPA shell, sets `requires_rendering` and
withholds the health score. A green audit of a page a static crawler could not read is worse
than no audit.

**3. Turn rendering on selectively, not everywhere.** In the crawler config:

```json
{"rendering": {"mode": "js", "escalation": {"sample_per_pattern": 2, "max_render_urls": 30}}}
```

Two URLs per detected template pattern are probed raw-versus-rendered; only patterns that
actually differ are escalated. Rendering every page of a 3000-URL site to find the one template
that hydrates its links costs an order of magnitude more for the same answer.

```bash
seohead crawl-site --url https://example.com --config ./crawl.json --out-dir ./run
```

**4. Every page records how it was measured.** `representation` is `static`, `rendered` or
`legacy_fragment` per page, so a report never silently mixes two populations of numbers.

## What comes out

```json
{
  "js_dependent": true,
  "raw": {"internal_links": 0, "words": 12},
  "rendered": {"internal_links": 34, "words": 812},
  "empty_shell": true
}
```

Zero links raw and 34 rendered is the whole finding: every crawler that does not execute
JavaScript sees a dead end.

## What it costs

A headless browser per rendered URL — seconds each, not milliseconds, and real memory. That is
why escalation samples patterns instead of rendering everything. The static crawl costs one
request per page as usual.

## What it cannot answer

- **What Google actually rendered.** This is a headless Chromium, not Googlebot's renderer, on
  a different schedule with different budgets. It answers "is this content JS-dependent",
  which is the actionable half.
- **Whether rendering delay costs rankings.** Nobody outside Google can measure that.
- **Field performance.** LCP and CLS here are lab numbers from one machine on one connection.
- **Anything behind a login.** Attaching a real browser profile crawls as whoever's cookies it
  carries, which is off by default and refused without an explicit directory.
