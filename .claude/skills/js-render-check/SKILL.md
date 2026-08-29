---
name: js-render-check
description: >-
  Compares raw HTML (what a bot receives without rendering) with the rendered DOM to show
  what appears on the page ONLY after JavaScript: text, internal links, title/canonical,
  h1, and Schema.org. This is critical when content, internal linking, or directives arrive
  only during rendering: Google renders with a delay, Yandex handles it less reliably, and
  AI crawlers almost never render. It also captures lab metrics (TTFB, FCP, LCP, CLS).
  Triggers: JS rendering, view-source vs rendered, content only after JS, client-side
  rendering, CSR, SPA SEO, Next.js rendering, check rendering, raw vs rendered, hydration,
  empty HTML, Core Web Vitals, LCP, CLS.
---

# JS Render Check — What Is Visible on the Page Only After JavaScript

Screaming Frog measures **one** snapshot—raw or rendered, depending on whether JS
Rendering is enabled—but does not compare "before JS" with "after JS." This skill
performs exactly that diff.

## When to Use It
- "Do content / links / metadata appear only after JS?"
- SPA / Next.js / Nuxt / CSR: "Will it be indexed?" or "Is SSR required?"
- An SF crawl differs with JS Rendering enabled versus disabled, and you need to determine
  which count is correct.
- A regional or silo audit found zero links where links are known to exist.

## Workflow

**One command instead of manually using curl and headless Chrome:**
```bash
seohead render-check --url https://example.com
```
Use a mobile viewport and device emulation where the layout differs:
```bash
seohead render-check --url https://example.com --viewport mobile
```

Returned fields:

| Field | Meaning |
|---|---|
| `raw` / `rendered` | identically calculated snapshots of both documents: words, internal links, title, h1, canonical, JSON-LD types, and size |
| `empty_shell` | ID of an empty single-page application container, if present |
| `js_dependent` | whether the page depends on scripts in any way |
| `metrics_lab` | TTFB, FCP, **LCP**, **CLS**, load, and weight—**lab data**, not field data |
| `findings` | ready-to-use written conclusions |

## How to Interpret Findings

| Finding | Severity | Action |
|---|---|---|
| "empty `<div id="root">` container" | critical | use SSR or prerendering: without rendering, the bot sees an empty page |
| "N% of text appears only after JS" | critical when >50% | move the primary content into the server response |
| "links appear only after JS" | critical | site traversal breaks: the crawler cannot reach deeper pages |
| "title is changed by a script" | critical | an unpredictable title may appear in search results |
| "canonical is injected by a script" | critical | the directive must not depend on rendering |
| "Schema.org appears only after JS" | warning | rich results are uncertain |
| "rendering changes nothing" | okay | SSR works; no further investigation is needed |

## Alert Threshold
The tool raises an alert at **30% and above**; a 5% increase is a widget, not a problem.
Zero words in raw HTML versus hundreds after rendering produces a separate, stronger finding.

## Metrics: Lab Data ≠ Field Data
`metrics_lab` is one run by one Chromium instance from this machine over this connection.
Field Core Web Vitals come from the Chrome UX Report and Search Console; one cannot substitute
for the other. A lab LCP on a fast Mac says nothing about a user's LCP over a mobile connection.
Lab numbers are useful **comparatively**: before versus after a fix, and page versus page.

## Why Wait for `load` Instead of `networkidle`
`networkidle` waits for 500 ms of network silence. A live commercial site never becomes
silent: analytics, chat widgets, and advertising keep connections open. In a measurement
on a production retail site, `load` returned a result in 6.4 seconds, while `networkidle`
timed out after 26 seconds. Google does not wait for network silence while rendering either.
Change this only for a specific case:
```bash
seohead render-check --url https://example.com --wait networkidle
```

## Boundaries
- **One run, one page.** Rendering an entire site is an SF crawl with JS Rendering
  enabled, not a job for this tool.
- **No Playwright means no rendering.** The tool returns `ok: false` and an installation
  command instead of misrepresenting the result:
  ```bash
  pip install 'seohead[render]' && python -m playwright install chromium
  ```
- **It does not fix the issue.** The finding "content is client-rendered" is a diagnosis;
  the solution (SSR, SSG, or prerendering for bots) depends on the stack.

## Related Skills
`sf-config` (enable JS Rendering in the crawl if the diff reveals client-rendered content) ·
`regional-audit` (`--render` when the city selector is rendered by a script) ·
`schema-graph` (markup found only in the DOM) · `silo-audit` (internal linking that is
absent from the raw HTML).
