# SEO Audit — example.com

- **Date:** 2026-06-21T17:39:00Z
- **Mode:** parse-exports  ·  **Profile:** full
- **Source:** examples/exports
- **Exports used:** internal_all, inlinks_4xx

## Health Summary

**Health score: 25 / 100**

- Crawled URLs: **6** (HTML: 5, indexable: 4)
- Total issues: **18**

| Severity | Count |
|---|---:|
| 🔴 Critical | 3 |
| 🟡 Warning | 10 |
| ⚪ Notice | 5 |

**Most frequent issues:**

| Check | Count | Severity |
|---|---:|---|
| `DESC_DUPLICATE` | 2 | warning |
| `TITLE_DUPLICATE` | 2 | warning |
| `TITLE_TOO_SHORT` | 2 | notice |
| `BROKEN_INTERNAL_LINK` | 1 | critical |
| `BROKEN_PAGE_4XX` | 1 | critical |
| `CANONICAL_MISSING` | 1 | warning |
| `DESC_MISSING` | 1 | warning |
| `DESC_TOO_SHORT` | 1 | notice |
| `H1_MULTIPLE` | 1 | warning |
| `HTML_BLOAT` | 1 | notice |
| `LARGE_HTML` | 1 | warning |
| `LOW_TEXT_RATIO` | 1 | notice |

**HTML size:** median 76 KB, p90 229 KB, p95 261 KB, max 293 KB.

## 🔴 Critical (3)

### `BROKEN_INTERNAL_LINK` — Internal Link Points to a 4xx URL (1)

| Destination | Status | Source | Anchor | Position | XPath |
|---|---:|---|---|---|---|
| https://example.com/old-page | 404 | https://example.com/ | Legacy Page | Content | `/html/body/main/article/p[3]/a` |
| https://example.com/old-page | 404 | https://example.com/page-a | view pump specifications | Footer | `/html/body/footer/nav/a[2]` |

> _How to fix:_ Replace the link with the current URL or add a 301 redirect. If the link appears in the footer or navigation, update the shared template.

### `BROKEN_PAGE_4XX` — Page Returns a 4xx Status (1)

| URL | Details |
|---|---|
| https://example.com/old-page | status=Not Found, inlinks=4 |

> _How to fix:_ Restore the page or redirect it to a relevant URL with a 301 response; remove links that still point to the broken URL.

### `TITLE_MISSING` — Title Is Missing (1)

- https://example.com/no-title

> _How to fix:_ Add a unique, descriptive title.

## 🟡 Warning (10)

### `CANONICAL_MISSING` — Indexable Page Has No Canonical URL (1)

- https://example.com/no-title

> _How to fix:_ Add a `<link rel="canonical">` element.

### `DESC_DUPLICATE` — Duplicate Meta Description (2)

- **“A sample description over seventy characters that reliably meets the configured audit threshold.”** — 2 URLs:
    - https://example.com/
    - https://example.com/page-b

> _How to fix:_ Write a unique description for each page.

### `DESC_MISSING` — Meta Description Is Missing (1)

- https://example.com/no-title

> _How to fix:_ Add a description of up to approximately 160 characters.

### `H1_MULTIPLE` — Multiple H1 Elements on One Page (1)

| URL | H1 Texts |
|---|---|
| https://example.com/page-a | Pump Models ⏐ Second H1 Heading |

> _How to fix:_ Keep one H1 and change the remaining top-level headings to H2 or H3.

### `LARGE_HTML` — Oversized HTML in Absolute or Relative Terms (1)

| URL | Size | × Median | Rank |
|---|---:|---:|---:|
| https://example.com/no-title | 293 KB | ×3.87 | 1 |

> _How to fix:_ Reduce HTML size by moving inline styles and scripts, removing base64 payloads, and simplifying redundant markup.

### `SLOW_RESPONSE` — Slow Server Response (1)

| URL | Details |
|---|---|
| https://example.com/no-title | response_time=2.0, max_s=1.5 |

> _How to fix:_ Improve TTFB by optimizing the server and cache configuration.

### `THIN_CONTENT` — Thin Content (Low Word Count) (1)

| URL | Details |
|---|---|
| https://example.com/page-b | word_count=50, threshold=200 |

> _How to fix:_ Expand the content or exclude the page from indexing.

### `TITLE_DUPLICATE` — Duplicate Title (2)

- **“Industrial Pumps Product A”** — 2 URLs:
    - https://example.com/page-a
    - https://example.com/page-b

> _How to fix:_ Write a unique title for each page.

## ⚪ Notice (5)

### `DESC_TOO_SHORT` — Meta Description Is Below the Length Threshold (1)

| URL | Details |
|---|---|
| https://example.com/page-a | length=7, min_chars=70 |

> _How to fix:_ Expand the description.

### `HTML_BLOAT` — Bloated HTML: High Byte Count with Little Text (1)

| URL | Details |
|---|---|
| https://example.com/page-b | bytes_per_word=1600.0, site_median_bpw=375.0, word_count=50, size_bytes=80000 |

> _How to fix:_ Reduce bytes per word by moving styles and scripts out of the HTML and removing base64 payloads.

### `LOW_TEXT_RATIO` — Low Text-to-HTML Ratio (1)

| URL | Details |
|---|---|
| https://example.com/page-b | text_ratio=8.0, threshold=10 |

> _How to fix:_ Increase the proportion of meaningful text content.

### `TITLE_TOO_SHORT` — Title Is Below the Length Threshold (2)

| URL | Details |
|---|---|
| https://example.com/page-a | title=Industrial Pumps Product A, length=26, min_chars=30 |
| https://example.com/page-b | title=Industrial Pumps Product A, length=26, min_chars=30 |

> _How to fix:_ Expand the title to an informative length.

## Sitemap & robots

- Declared in robots.txt: **None**
- URLs in sitemap: **0**  ·  indexable URLs in crawl: **4**
- In sitemap but not in crawl: **0**  ·  in crawl but not in sitemap: **0**
- Non-200 URLs in sitemap: **0**  ·  non-indexable URLs in sitemap: **0**
