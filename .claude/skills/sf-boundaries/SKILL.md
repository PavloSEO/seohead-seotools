---
name: sf-boundaries
description: >-
  A navigation reference explaining what an SEO audit obtains THROUGH Screaming
  Frog, what SF CANNOT do, and what must be handled by an agent or other tools. It
  routes each need to the appropriate skill/tool (status codes/meta/canonicals/
  duplicates/sitemaps/broken links use sf-analyzer; WHOIS/hosting/CDN/CMS use
  seo-recon; JS-rendered vs raw HTML uses js-render-check; meaning/E-E-A-T needs manual
  agent review; silos use silo-audit; H1-H6 uses heading-outline; robots use
  robots-audit; CWV uses PSI API) and explains SF's limitations honestly. Use it when
  asked: what can Screaming Frog do, what can SF not do, SF boundaries, how to
  obtain something, SF vs agent, Screaming Frog capabilities, can Screaming Frog
  check X.
---

# SF Boundaries — What to Obtain Through Screaming Frog and What Falls Outside It

SF is a powerful crawler, but it is NOT a universal tool. This skill is a routing
map: for each "need," it shows immediately who handles it—SF (through
**sf-analyzer**), a dedicated agent skill, or an external API. Use it BEFORE an
audit so you do not try to extract metrics SF does not calculate and do not
manually duplicate data that SF provides at no additional cost.

## When to Use It
- "What can/can't Screaming Frog do?", "SF boundaries," or "SF vs agent";
- "How do I obtain <a specific need>?"—when the correct tool must be selected;
- when planning an audit and deciding what to crawl in SF and what to collect
  separately.

## Table: Need -> How to Obtain It
| Need | How to obtain it |
|---|---|
| HTTP status codes, redirect chains, response headers | **SF** -> `sf-analyzer` |
| Title/Description/meta robots, canonicals, hreflang attributes | **SF** -> `sf-analyzer` |
| Duplicates (exact / near-duplicate), Link Score, orphan pages | **SF** -> `sf-analyzer` (requires Crawl Analysis; see `sf-config`) |
| Sitemap: 3xx/4xx URLs in the sitemap, mismatches, stale `lastmod` | **SF** -> `sf-analyzer` |
| Broken links + their DOM location (source/destination/anchor/XPath) | **SF** -> `sf-analyzer` |
| HTML-size anomalies, heavy pages | **SF** -> `sf-analyzer` |
| WHOIS, domain age, hosting/ASN, geography, TLS | toolkit -> `seohead domain-profile` (`seo-recon`) |
| CDN in front of the site, cache behavior, HTTP/2-3, Brotli, TTFB | toolkit -> `seohead cdn-check` (`seo-recon`) |
| CMS/framework, analytics, pixels, third-party scripts | toolkit -> `seohead tech-detect` (`seo-recon`) |
| Security headers, version disclosure, cookie flags, `.git`/`.env` | toolkit -> `seohead security-check` (`security-audit`) |
| Backlinks from your own donor list: whether each is live and dofollow | toolkit -> `seohead backlinks-check` (`backlinks-check`) |
| JS-rendered vs raw HTML (what a bot sees without JS) | agent -> `js-render-check` |
| Content quality, meaning, E-E-A-T, expertise | manual agent review (SF does not judge meaning) |
| Silo structure / semantic coverage / topical clusters | agent -> `silo-audit` |
| Complete H1-H6 outline and its logic | agent -> `heading-outline` |
| robots.txt analysis and interpretation | agent -> `robots-audit` |
| PageSpeed / Core Web Vitals (LCP/CLS/INP) | external -> **PSI API** |

## SF Limitations (Explain Them Honestly)
- **`.seospider` cannot be parsed directly**—it uses Java serialization. You need
  the licensed SF CLI (mode A) or a manual CSV export (mode B). See `sf-analyzer`.
- **It does not judge meaning**—SF measures Title length, checks for an H1, and
  checks spelling (if the module is enabled), but it does not evaluate expertise,
  usefulness, or E-E-A-T. That is an agent's job.
- **Rendering works only when the module is enabled**—without JS Rendering (see
  `sf-config`), SF sees raw HTML; content will be sparser on SPA/Next.js sites.
  `js-render-check` performs the "JS vs raw" comparison.
- **No WHOIS / hosting / CMS data**—SF does not know the domain's age, ASN, CDN, or
  site engine. Use `seo-recon` for that.
- **It does not test cache behavior dynamically**—SF sees the headers from one
  response, but it does not issue repeated and conditional requests to determine
  whether the CDN actually caches the page. Use `seohead cdn-check` for that.
- **It does not assess security**—its reports do not cover security headers,
  cookie flags, or version disclosure. Use `seohead security-check` for that.
- **It knows nothing about inbound links**—SF crawls your site, not other sites.
  Use `seohead backlinks-check` to check donors; a complete backlink profile
  requires external databases.
- **CWV is not its job**—SF does not calculate a PageSpeed field; obtain it from
  the PSI API.

## Workflow (Fast Routing)
1. **State the need** as one item and find its row in the table above.
2. **If the cell says SF** -> do not collect it manually; run the audit:
   `seohead sf run --crawl https://example.com --out report --tasks`. If a check
   returns `skipped` (MIXED_CONTENT, STRUCTURED_DATA, SPELLING, DOM_*), its module
   is disabled; fix that through `sf-config`, not with an agent.
3. **If the cell says agent/external** -> SF will not help; route it to the correct
   skill / API:
   - `seo-recon` (domain/hosting/CDN/stack)—use the toolkit, not manual checks:
     `seohead domain-profile --domain example.com`,
     `seohead cdn-check --url https://example.com`,
     `seohead tech-detect --url https://example.com`.
     Manual fallback (only if the toolkit is unavailable): `whois`, `dig +short`,
     `curl -sI ... | grep -iE 'server|cf-ray|x-powered-by'`.
   - `security-audit`: `seohead security-check --url https://example.com`
     (`--probe-paths`—when asked to check for exposed `.git`/`.env` paths).
   - `js-render-check`: compare the raw and rendered DOM—
     `curl -s https://example.com/page > raw.html` against the rendered output
     (headless/SF JS Rendering); diff the number of `<a>`/`<h1>` elements and the
     text volume; a discrepancy > ~30% means the content depends on JS.
   - `robots-audit`—analyze `curl -s https://example.com/robots.txt`.
   - `heading-outline`—the complete H1-H6 outline; `silo-audit`—clusters;
     meaning/E-E-A-T—the agent handles these directly.
   - CWV -> PSI API:
     `curl -s "https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=https://example.com&strategy=mobile&category=performance"`
     -> read `loadingExperience.metrics` (LCP/CLS/INP) and
     `lighthouseResult.categories.performance.score`.
4. **TLS/certificate expiration** (neither SF nor WHOIS), when needed—
   `echo | openssl s_client -connect example.com:443 -servername example.com 2>/dev/null | openssl x509 -noout -dates`.

## What to Deliver to the User
- A concise verdict for each need: "SF handles this" / "this is outside SF; use
  <skill/API>."
- If everything is within SF's scope, route the user directly to `sf-analyzer`
  (+ `sf-config` if anything is `skipped`).
- If some items fall outside SF, provide the "need -> tool -> command" list from
  step 3 so an agent or person can collect the missing data without trying to
  extract it from the crawl.
