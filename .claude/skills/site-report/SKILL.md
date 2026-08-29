---
name: site-report
description: >-
  Runs a bulk site audit with one command and produces a ready-made report: Excel
  (4 worksheets, filters, chart), Word (for the client), CSV (for the tracker), or
  Markdown. Site-level tools run once, while page-level tools run for every URL in
  the sitemap; everything is consolidated into one JSON document from which a file
  in any supported format can be built. Triggers: "full-site audit," "Excel
  report," "Word report," "export to CSV," "bulk audit," "check the entire site,"
  "client report," "build a report," "xlsx," "docx," "site audit," "SEO report."
---

# Site Report — From Domain to File

The consolidation is implemented in code: one call assembles the evidence document,
and a second call turns it into a file.

## Workflow

**Everything at once — audit and Excel in a single command:**
```bash
seohead site-audit --url https://example.com --limit 50 --report xlsx --out audit.xlsx
```

**Two steps when multiple reports are needed:**
```bash
seohead site-audit --url https://example.com --limit 100 > audit.json
seohead report-build --audit audit.json --format docx --out client.docx
seohead report-build --audit audit.json --format csv  --out tasks.csv
```

**A custom page list instead of the sitemap** (for example, landing pages from the
semantic keyword set):
```bash
seohead site-audit --url https://example.com --urls "https://example.com/a,https://example.com/b"
```

## What Runs

| Level | Tools | Number of Runs |
|---|---|---|
| Site | domain, CDN and cache, stack, security, robots, AI crawlers, llms.txt, regions, rendering, sitemap | once |
| Page | `parse`, `schema-check`, `social-meta-check` | for every URL |

The URL list comes from the sitemap, whose address is read **from robots.txt**. If
there is no sitemap, at least the home page is analyzed, and this is reflected in
`pages_checked`.

## Flags That Actually Change the Result

| Flag | When It Is Needed |
|---|---|
| `--limit N` | 25 pages by default. Increase it deliberately on a large site: this generates N×3 requests |
| `--concurrency N` | 5 by default, with a ceiling of 10. The audit must not resemble a load test |
| `--render` | a script renders the city switcher (requires Playwright) |
| `--skip` | avoid unnecessary checks: `--skip render_check,regions_check` |

## How to Read the Result

**Start with `summary.tools_failed`.** This is the most important field: it lists
the checks that did not run successfully. Their silence does **not** mean "no issues
found." All four formats print this block separately, and the report should be read
starting with it.

**Then read `findings` by level.** `critical` means the issue is preventing ranking
right now (the crawler sees an empty page, the canonical points to another host, or
the page is noindexed). `warning` means the issue causes interference or wastes the
crawl budget. `notice` is an observation.

**The level is assigned by rules, not measured.** The rule table is
`SEVERITY_RULES` in `seohead/audit/site.py`; order matters (the first match wins).
The document states this explicitly in `summary.severity_note`. If the client
disagrees with a priority, the rule can be shown and discussed.

## Which Format Is for Whom

| Format | Audience | Why |
|---|---|---|
| `xlsx` | you and the developers | filters, sorting, a live Excel chart, and findings distributed one per row |
| `docx` | the client | text with headings: conclusion first, then evidence |
| `csv` | the tracker | two files (findings and `*.pages.csv`), `;` and BOM — otherwise Excel displays garbled characters |
| `md` | Git and correspondence | readable anywhere |

## Boundaries
- **There is no crawler.** The audit runs against the sitemap or your custom list.
  Use Screaming Frog for a full-site crawl; see `sf-analyzer`.
- **The report does not calculate anything.** The generators only arrange JSON into
  worksheets and paragraphs. If a number is absent from the document, it will also
  be absent from the report.
- **Compare repeat runs manually.** There is currently no audit delta: save
  `audit.json` with the date in its filename.

## Templates
[`examples/reports/`](../../../examples/reports/README.md) contains `minimal.json`,
`full.json`, and a field-by-field explanation of the contract. It also shows what
to populate when the document is assembled by custom code rather than by the
audit.

## Related Skills
`sf-analyzer` (when a full crawl rather than a sitemap is needed) · `sf-tasks`
(backlog from a crawl audit) · `regional-audit` · `js-render-check` · `seo-recon`.
