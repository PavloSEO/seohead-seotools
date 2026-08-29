# audit.seospiderconfig Checklist — Module -> Checks

Enable these settings once in Screaming Frog (`Configuration → …`), then save the
configuration as `audit.seospiderconfig` in the repository root. The tool will
load it automatically.

| SF module | Where to enable it | Checks it unlocks | Data source |
|---|---|---|---|
| **Spelling & Grammar** | Configuration → Content → Spelling & Grammar → Enable (+ language) | `SPELLING_ERRORS`, `GRAMMAR_ERRORS`, `LONG_SENTENCES`, `READABILITY_DIFFICULT` | Internal:All columns (Spelling/Grammar/Flesch/Readability/Avg Words) |
| **Structured Data** | Configuration → Spider → Extraction → Structured Data → JSON-LD + Microdata + RDFa + Schema.org + Google Validation | `SCHEMA_VALIDATION_ERROR`, `STRUCTURED_DATA_MISSING` | Internal:All (Structured Data, Validation Errors) + Structured Data tabs |
| **Security** | normal crawl + JS rendering; for resources: Crawl → Check Links Outside Start Folder | `MIXED_CONTENT`, `MISSING_HSTS` | Security tab (export-tabs) |
| **Images** | enabled by default; thresholds: Configuration → Spider → Preferences | `IMG_OVER_KB`, `IMG_MISSING_DIMENSIONS`, `IMG_MISSING_ALT` | Images tabs (export-tabs) |
| **Store HTML / Rendered HTML** | Configuration → Spider → Extraction → Store HTML + Store Rendered HTML | `DOM_TOO_DEEP`, `DOM_TOO_MANY_NODES` | saved HTML (set `input.html_store_dir`) |
| **JavaScript Rendering** | Configuration → Spider → Rendering → JavaScript | accuracy of all on-page checks on SPA/Next.js sites | rendered output instead of raw HTML |
| **Crawl Linked XML Sitemaps** | Configuration → Spider → Crawl → XML Sitemaps → Crawl Linked XML Sitemaps | `SITEMAP_ORPHAN`, `SITEMAP_URL_4XX_5XX`, `SITEMAP_URL_NON_INDEXABLE`, `URL_NOT_IN_SITEMAP` | `Sitemaps:*` tabs |
| **Crawl Analysis (automatic)** | Crawl Analysis → Configure → Auto Analyse At End of Crawl | `NEAR_DUPLICATE`, `ORPHAN_PAGE`, Link Score | SF post-processing |

## Verify That It Works
After creating the config:
```bash
seohead sf doctor                 # Was SF found? Are dependencies available?
seohead sf run --crawl https://example.com --out report --tasks -v
```
In `report/audit.json`, `run.checks_skipped` should **decrease**: checks that were
`skipped` because of "no … column / no … export" will no longer be skipped once
the module is enabled.

## Export Profiles (full vs lite)
- **full (default)** exports the Structured Data / Security / Images / Sitemaps
  tabs. They are populated only when the corresponding module is enabled in
  `audit.seospiderconfig`; without it, the export is empty and the check is
  `skipped` (without errors).
- **lite** (`--profile lite`) is a fast minimum for regular monitoring.

## Important
- Only SF can create `.seospiderconfig` (binary format). One file works for every
  site.
- Place it in the repository root (or specify the path in
  `config.json → sf_cli.seospiderconfig`).
- Do not commit it if it contains your integration API keys (GA/GSC). By default,
  it contains no keys.
