# Screaming Frog CLI — What to Export (Cheat Sheet)

CLI exports, headless mode, and `--load-crawl`/`--save-crawl` require a **paid SF
license**. The free version does not support CLI exports and has a 500-URL limit.

## Basic Command (Windows)

```bat
ScreamingFrogSEOSpiderCli.exe ^
  --headless ^
  --load-crawl "site.seospider" ^      REM or --crawl https://example.com / --crawl-list urls.txt
  --config "audit.seospiderconfig" ^    REM profile: Crawl Linked XML Sitemaps, Store HTML, Structured Data, JS rendering
  --output-folder "exports" ^
  --export-format csv ^
  --timestamped-output ^
  --export-tabs "Internal:All,Response Codes:Client Error (4xx),H1:Multiple" ^
  --bulk-export "Response Codes:Client Error (4xx) Inlinks" ^
  --save-report "Crawl Overview,Redirects:Redirect Chains"
```

## Minimum for Mode B (Manual Export)

Even `Internal:All` alone is sufficient. The more you export, the more complete
the audit will be:

| What | Why |
|---|---|
| **Internal → All** | Master table; the foundation for almost all checks and page-size heuristics |
| Response Codes → Client Error (4xx) / Server Error (5xx) / Redirection (3xx) | Response codes |
| **Bulk: Client Error (4xx) Inlinks** (plus 5xx/3xx Inlinks) | Broken links: source, anchor, Link Position, and Link Path (XPath) |
| Sitemaps → URLs In Sitemap / Not In Sitemap / Orphan URLs / Non-Indexable In Sitemap | Sitemap module (requires Crawl Analysis + Crawl Linked XML Sitemaps) |
| Images → Missing Alt Text | Alt-text issues |
| Reports → Crawl Overview / Redirect Chains | Cross-checking counts and redirect chains |

## Pitfalls
- **Crawl Analysis** must complete; otherwise, Sitemaps / Near Duplicates / Orphan
  will be empty.
- The **Sitemaps** tab is empty unless "Crawl Linked XML Sitemaps" is enabled in
  the configuration.
- `All Inlinks` is enormous on large sites. Targeted `*:Inlinks` exports for
  3xx/4xx/5xx are sufficient for broken links. In our tool, use the
  `--fetch-all-inlinks` flag.
- SF often writes CSV files in UTF-16 or UTF-8 with BOM; the loader handles both.
  XLSX avoids the issue entirely.
- Exact filter labels vary between versions; verify them against the GUI or SF
  19.x `--help` output.
