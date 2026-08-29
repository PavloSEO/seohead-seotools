---
name: regional-audit
description: >-
  Audits a website's regional structure: subdomains (msk.example.com), directories
  (example.com/msk/), and satellite sites on separate domains. Finds the city switcher,
  recognizes approximately 100 Russian cities by slug and Russian anchor text, checks
  every regional version, and catches issues that destroy regional search visibility:
  redirects to the main site, canonicals pointing to another host, duplicate content,
  and one telephone number for the entire country. Triggers on: “regions,” “city
  subdomains,” “branches,” “satellite sites,” “regional SEO,” “multi-region,” “cities,”
  “Yandex region,” “affiliates,” “msk.example.com,” and “region subdomains.”
---

# Regional Audit — Cities, Subdomains, and Satellite Sites

Regional targeting in the Russian-language web is implemented using three mutually
incompatible approaches. Half of the resulting problems come from choosing an approach
without considering the consequences or from mixing two approaches at once.

| Approach | Example | Region in Yandex Webmaster | Cost of a Mistake |
|---|---|---|---|
| Subdomain | `msk.example.com` | one per host | each city needs its own content |
| Directory | `example.com/msk/` | **one for the entire website** | the city is established only through page text |
| Satellite site | `example-msk.example` | its own region, but also its own authority | sites may be grouped as affiliates |

The key point people confuse is that **directories have one Yandex Webmaster region for
the entire domain**. You cannot assign Moscow to `/msk/` and Saint Petersburg to `/spb/`.
Directories work only through the text on the page. Subdomains are separate hosts, and
each host can be assigned its own region.

## When to Use It
- A client has “branches throughout Russia,” but traffic comes from only one city.
- Before selecting a regional SEO approach, to avoid rebuilding the structure later.
- When satellite sites exist and you need to determine whether Yandex may group them as affiliates.
- Regional pages exist but do not rank, and the reason is unclear.

## Workflow

**Step 1. Capture the structure.** The tool automatically finds the city switcher on the page:
```bash
seohead regions-check --url https://example.com
```

**Step 2. Add what cannot be seen on the page.** Satellite sites on separate domains are
almost never included in a city switcher, so always supply them manually:
```bash
seohead regions-check --url https://example.com --extra "https://example-msk.example/,https://example-spb.example/" --limit 20
```

**Step 3. Read `findings`.** Their order roughly corresponds to severity:

| Finding | What It Means |
|---|---|
| “redirect to the main site” | the region does not actually exist: there is a host but no page |
| “canonicalized to another host” | the page has removed itself from the index |
| “noindex on regional pages” | the same outcome, but explicit |
| “content matches” | cities differ only by address, causing cannibalization |
| “identical title” | the city is not inserted into the title |
| “same telephone number in every region” | a signal to Yandex that the branches do not exist |
| “two approaches at once” | subdomains and directories compete with one another |
| “on separate domains” | check for affiliate grouping manually |

**Step 4. If zero regions are found**, this does not mean that everything is fine. The
tool says so explicitly: a script often renders the city switcher, so it is absent from
the raw HTML. In that case, run:
```bash
seohead render-check --url https://example.com      # inspect what appears only after JavaScript runs
```
Then repeat the audit with `--extra`, using the cities found in the rendered DOM.

## What the Tool Checks on Every Regional Page
Status and redirect chain · final URL · `canonical`, including whether it points to the
same host · `noindex` in meta and `X-Robots-Tag` · `title` and `h1` · whether the city is
mentioned in `title` · text volume · telephone numbers in numeric form · content
similarity to other regions (SimHash, threshold 0.95).

## Boundaries — What the Tool Does Not Do
- **It does not assign regions in Yandex Webmaster.** This is a manual operation in the
  Yandex interface.
- **It does not determine affiliate grouping.** It shows signals such as identical
  contact details and content across different domains; only the search results can
  support the conclusion that sites have been grouped.
- **It does not see a JavaScript city switcher** without `render-check`, and it states
  this limitation explicitly.
- **It does not invent cities.** An unfamiliar slug is treated as non-regional, not as
  “probably a city.”

## City Reference
`seohead/recon/regions.py` contains `REGION_SLUGS` for approximately 100 cities; spelling
variants such as `msk`/`moskva`/`moscow` collapse into one region. It also contains
`REGION_NAMES`, a reverse index of Russian city names used to recognize anchor text. Add
a new city with one `_region(...)` line.

Service subdomains such as `www`, `api`, `cdn`, and `lk`, and common first path segments
such as `/catalog/`, `/blog/`, and `/ru/`, are never treated as regions. The
`NON_REGION_HOSTS` and `NON_REGION_PATHS` lists are defined in the same module.

## Related Skills
`seo-recon` identifies domain ownership and hosting, which matters for satellite sites ·
`duplicate-audit` applies the same SimHash approach to the entire website ·
`js-render-check` handles city switchers rendered by scripts ·
`silo-audit` examines internal linking within a region.
