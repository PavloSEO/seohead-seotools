# `audit.json` Contract (Brief)

Formal schema: `seohead/sf/schema/audit.schema.json` (JSON Schema 2020-12).
The output is validated in tests. Encoding is UTF-8, `ensure_ascii=false`, with an indent of 2.

## Top Level

```jsonc
{
  "schema_version": "2.0",
  "tool":    { "name", "version", "generated_by" },
  "run":     { "project", "input_mode", "source", "sf_version_detected",
               "generated_at", "profile", "exports_used", "exports_missing",
               "checks_skipped": [ { "id", "reason" } ] },
  "summary": { "totals", "by_severity": {critical,warning,notice},
               "by_check", "health_score", "size_stats_bytes", "sitemap" },
  "issues":  [ /* Issue */ ],
  "pages":   [ /* Page */ ],
  "groups":  [ /* Group */ ]
}
```

## Issue (Issue-Centric)

```jsonc
{
  "id": "ISSUE-000123",
  "fingerprint": "ab12cd34ef56",          // Stable hash for comparing runs
  "check": "BROKEN_INTERNAL_LINK",
  "severity": "critical",                  // critical | warning | notice
  "source": "inlinks:Client Error (4xx) Inlinks",
  "message": "An internal link points to a 4xx URL",
  "target_url": "https://site/old-page",   // Link target (broken)
  "status_code": 404,
  "occurrences_count": 5,                   // Number of pages on which it occurs
  "locations": [                            // WHERE it occurs, WHERE it points + DOM
    { "source_url", "anchor", "alt_text", "link_position", "link_path",
      "follow", "rel", "target" }
  ],
  "details": { /* Per-check data: h1_texts, size_bytes/ratio/rank, ... */ },
  "group_id": "GRP-TITLE-0007",            // Reference to groups[] for duplicates
  "fix_hint": "…",
  "evidence": { "export": "…inlinks.csv" }
}
```

## Page (Page-Centric)

`url`, `status_code`, `indexability`, `content_type`, `metrics{…}`, `issues[]`
(check codes), `issue_ids[]`. `metrics` always contains the derived signals
`size_bytes`, `size_vs_median_ratio`, `bytes_per_word`, `dom_depth`, `dom_nodes`,
`text_ratio`, `inlinks`, `crawl_depth`, `word_count`, `is_in_sitemap`,
`sitemap_lastmod`, and `response_time`, even when the threshold is not exceeded.

## Group (Duplicates/Shared Values)

`group_id`, `check`, `value`, `urls[]`, `count` — groups of identical Title/Desc/H1/Hash values.

## How to Read It

- Broken links and their DOM locations: entries in `issues[]` where `check` ∈
  {`BROKEN_INTERNAL_LINK`,`LINK_TO_5XX`,`INTERNAL_LINK_TO_REDIRECT`}, using the `locations` field.
- “Which two H1s, and where?”: `check=H1_MULTIPLE`, `details.h1_texts`.
- Size anomalies: `check=LARGE_HTML`, `details.{size_bytes,site_median,ratio,rank}`.
- Sitemap: `summary.sitemap` + `check` ∈ `SITEMAP_*` / `URL_NOT_IN_SITEMAP`.
- What was not calculated and why: `run.checks_skipped`.
