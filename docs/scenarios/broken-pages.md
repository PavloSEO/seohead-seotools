# Scenario 11 — Broken pages: what 404s, what 500s, and what never answered at all

## The question

> Support keeps forwarding emails about dead links. Which pages are actually broken, and who
> is linking to them?

Three different failures arrive inside the same complaint. A 4xx is a page that is gone, a 5xx
is a page that exists and is failing, and no response at all is not a status code — it is the
absence of one. Each needs a different person to fix it, so this chain keeps them apart.

## Covers

- **Response Codes** — Internal No Response · Internal Client Error (4XX) · Internal Server Error (5XX)

## The chain

**1. Crawl once, with a config file rather than flags alone.** The config is the record of what
was measured, and the rate chosen in it decides whether the 5xx list below describes the site
or describes your crawl.

```bash
seohead crawl-site --url https://example.com --config ./crawl.json --out-dir ./run
```

**2. Scan the run before reading a single finding.**

```bash
seohead log-scan --run ./run
```

Exit 2 means the run's own numbers disagree with each other. A broken-page list produced by a
run that contradicts itself is a list somebody will chase for a day.

**3. Split the findings by what actually broke.** `audit.json`'s `summary.by_check` separates
the page that failed from the link that points at it:

| Check | What it is |
|---|---|
| `BROKEN_PAGE_4XX` | the URL itself returns 4xx |
| `SERVER_ERROR_5XX` | the URL itself returns 5xx |
| `NO_RESPONSE` | timeout, DNS or connection failure, recorded with status 0 |
| `BROKEN_INTERNAL_LINK` | a page on the site links to a 4xx URL |
| `LINK_TO_5XX` | a page on the site links to a 5xx URL |

The last two carry `locations`: the source URL, the anchor text and, when link-position
classification is enabled, whether the link sits in content or in a shared footer. A footer
link is one template edit; twelve content links are twelve edits.

**4. Reproduce the worst ones live, one at a time.**

```bash
seohead redirects-check --url https://example.com/old
```

The chain comes back hop by hop with the status of each, so a "404" that is really a 302 into a
404 stops being reported as a missing page.

**5. Check that a working page is not a disguised error.**

```bash
seohead soft404-check --url https://example.com/missing
```

A template that answers 200 with "nothing found" inside it never appears in any status-code
list, which is exactly why it survives for years.

**6. Hand it over.**

```bash
seohead report-build --audit ./run/audit.json --format xlsx --out ./broken-pages.xlsx
```

## What comes out

One finding per broken destination, with every place that links to it attached — the shape a
developer can work through from the top:

```json
{
  "check": "BROKEN_INTERNAL_LINK",
  "severity": "critical",
  "message": "Internal link points to a 4xx URL",
  "target_url": "https://example.com/old-page",
  "status_code": 404,
  "occurrences_count": 2,
  "locations": [
    {"source_url": "https://example.com/", "anchor": "Legacy Page",
     "link_position": "Content"},
    {"source_url": "https://example.com/page-a", "anchor": "specifications",
     "link_position": "Footer"}
  ]
}
```

Every finding also carries a `fix_hint`, which for this check names the case worth checking
first: a broken link in the footer or the navigation is one shared template, not one page.

## What it costs

One request per URL at the rate the config sets, on one host. Nothing paid, and nothing sent
anywhere.

The rate is not a performance preference here, it is part of the measurement. A WordPress blog
crawled at 10 URL/s started returning 502 after 249 pages; at 3 URL/s the same site completed
all 3387 URLs. The first run's server-error list was a picture of the crawler.

## What it cannot answer

- **Whether a 404 is wrong.** A deleted page is supposed to return 404. The finding states the
  status; whether the URL should still resolve is a person's decision.
- **Whether a 5xx belongs to the site or to your crawl.** Re-request the failing URLs slowly
  and alone before reporting them. If they answer, you measured yourself.
- **Why nothing answered.** `NO_RESPONSE` carries the crawler's verdict, not a packet-level
  diagnosis: DNS failure, a TLS handshake that never finished and a hung connection all end in
  the same record.
- **Pages nothing links to.** A broken page with no inlinks is invisible to a link crawl — see
  [sitemap reconciliation](sitemap-reconciliation.md).
- **What the visitor saw.** A status code is not an error page. Whether the 404 template is
  useful, or silently sends everyone to the home page, is a separate question.
