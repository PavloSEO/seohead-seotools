# Check catalogue

Generated from `seohead/sf/core/registry.py` — do not edit by hand. Regenerate with:

```bash
python scripts/generate_checks_reference.py
```

**108 checks.** Severity, evidence and fix all come from the same `CHECKS` dict the rule engine reads, so this table cannot say something the engine disagrees with.

- **Fires on** — what the check id means, in the registry's own words.
- **Evidence** — the `source` tag: which export or module has to be present for the check to run at all; its absence is why a check comes back `skipped` instead of a silent pass.
- **Fix** — the remedy the audit ships next to the finding.

## 7.A — indexing & response codes

| Check id | Severity | Evidence | Fires on | Fix |
|---|---|---|---|---|
| `BROKEN_PAGE_4XX` | critical | SF:Response Codes:4xx | Page returns a 4xx response (broken page) | Restore the page or redirect it with a 301 to a relevant URL; remove or update links that point to it. |
| `SERVER_ERROR_5XX` | critical | SF:Response Codes:5xx | Page returns a 5xx response (server error) | Investigate the server or application; this error makes the page unavailable to users and crawlers. |
| `NO_RESPONSE` | critical | SF:Response Codes:No Response | No response (timeout, DNS, or connection failure) | Check host availability, DNS resolution, connectivity, and timeout settings. |
| `BLOCKED_BY_ROBOTS` | warning | SF:Response Codes:Blocked by Robots.txt | URL is blocked by robots.txt | Confirm that the block is intentional; pages intended for indexing should remain crawlable. |
| `NON_INDEXABLE_LINKED` | notice | SF-derived | Internally linked page is non-indexable | Decide whether the page should be indexable; otherwise remove unnecessary internal links and account for crawl-budget impact. |
| `IMPORTANT_URL_BLOCKED_BY_ROBOTS` | warning | SF-derived | Live page is blocked by robots.txt despite receiving internal links | robots.txt blocks crawling, not indexing, so link discovery is lost. Make the URL crawlable with a more specific Allow rule than the matching Disallow, and control indexing with canonical or noindex. A common case is pagination such as /blog?page=N blocked by Disallow: /*?. |
| `ROBOTS_BLOCKS_RESOURCES` | notice | sitemap | robots.txt blocks JavaScript or CSS resources required for rendering | Do not block .js, .css, or _next/static resources in robots.txt; otherwise Google may render the page incompletely. |

## 7.B — links & DOM localization

| Check id | Severity | Evidence | Fires on | Fix |
|---|---|---|---|---|
| `BROKEN_INTERNAL_LINK` | critical | inlinks:Client Error (4xx) Inlinks | Internal link points to a 4xx URL | Update the link to the current URL or add an appropriate 301 redirect; if it appears in the footer or navigation, fix the shared template. |
| `LINK_TO_5XX` | critical | inlinks:Server Error (5xx) Inlinks | Internal link points to a 5xx URL | Repair the destination page or remove the link. |
| `INTERNAL_LINK_TO_REDIRECT` | warning | inlinks:Redirection (3xx) Inlinks | Internal link points to a redirect (3xx) | Point the link directly to the final URL to eliminate the unnecessary redirect hop. |
| `BROKEN_EXTERNAL_LINK` | warning | inlinks:Client Error (4xx) Inlinks | External link points to a 4xx or 5xx URL | Update or remove the broken external link, while accounting for sites that intentionally return 403 responses to crawlers. |
| `EXTERNAL_LINK_TO_REDIRECT` | notice | inlinks:Redirection (3xx) Inlinks | External link points to a redirect (3xx) | This is often acceptable for external sites; optionally update the link to point directly to the final URL. |
| `REDIRECT_CHAIN` | warning | SF:report Redirect Chains | Redirect chain contains two or more hops | Replace the chain with a single 301 redirect to the final URL. |
| `REDIRECT_LOOP` | critical | SF:report Redirect Chains | Redirect loop detected | Break the redirect cycle so every redirect path terminates at a valid destination. |
| `BAD_REDIRECT_TYPE` | notice | SF-derived | Temporary redirect (302, 303 or 307) used where a permanent redirect is expected | Use a 301 redirect when the move is permanent. |

## 7.C — title & meta description

| Check id | Severity | Evidence | Fires on | Fix |
|---|---|---|---|---|
| `TITLE_MISSING` | critical | SF-derived | Title element is missing | Add a unique, descriptive title element. |
| `TITLE_DUPLICATE` | warning | SF-derived | Duplicate title element | Give each page a unique title element. |
| `TITLE_MULTIPLE` | warning | SF:Page Titles:Multiple | Multiple <title> elements | Keep exactly one <title> element in the document head. |
| `TITLE_TOO_LONG` | notice | SF-derived | Title exceeds the configured length threshold | Shorten the title to fit the configured character or pixel-width limit. |
| `TITLE_TOO_SHORT` | notice | SF-derived | Title falls below the configured length threshold | Expand the title to an informative length without padding it with boilerplate. |
| `TITLE_EQUALS_H1` | notice | SF-derived | Title is identical to the H1 | Differentiate the title and H1 by purpose, wording, or keyword emphasis. |
| `DESC_MISSING` | warning | SF-derived | Meta description is missing | Add a useful meta description, typically up to about 160 characters. |
| `DESC_DUPLICATE` | warning | SF-derived | Duplicate meta description | Write a unique meta description for each page. |
| `DESC_TOO_LONG` | notice | SF-derived | Meta description exceeds the configured length threshold | Shorten the description while preserving its primary value proposition. |
| `DESC_TOO_SHORT` | notice | SF-derived | Meta description falls below the configured length threshold | Expand the description with specific, useful page information. |

## 7.D — headings (incl. multiple H1)

| Check id | Severity | Evidence | Fires on | Fix |
|---|---|---|---|---|
| `H1_MISSING` | warning | SF-derived | H1 heading is missing | Add one H1 that clearly states the page topic. |
| `H1_MULTIPLE` | warning | SF:H1:Multiple | Multiple H1 headings on the page | Keep one primary H1 and demote the remaining headings to H2 or H3 as appropriate. |
| `H1_DUPLICATE` | notice | SF-derived | H1 is duplicated across multiple URLs | Use a unique, page-specific H1 on each URL. |
| `H1_TOO_LONG` | notice | SF-derived | H1 exceeds the configured length threshold | Shorten the H1 while retaining the page's main topic. |
| `H2_MISSING` | notice | SF-derived | Page has an H1 but no H2 headings | Add meaningful H2 subheadings where needed to structure the content. |

## 7.E — canonical & directives

| Check id | Severity | Evidence | Fires on | Fix |
|---|---|---|---|---|
| `CANONICAL_MISSING` | warning | SF-derived | Indexable page has no canonical URL | Add a valid <link rel="canonical"> element. |
| `CANONICALISED` | notice | SF-derived | Canonical points to a different URL | Confirm that cross-canonicalization is intentional and that the target is the preferred version. |
| `CANONICAL_NON_INDEXABLE` | warning | SF-derived | Canonical points to a non-indexable URL | Point the canonical to an indexable preferred version. |
| `NOINDEX` | notice | SF:Directives:Noindex | Page contains a noindex directive | Confirm that exclusion from indexing is intentional. |
| `NOFOLLOW_PAGE` | notice | SF:Directives:Nofollow | Page-level nofollow directive is present | Confirm the directive is intentional and review its effect on crawling and internal link equity. |
| `META_KEYWORDS_PRESENT` | notice | SF-derived | Obsolete meta keywords element is present | Remove it if desired; modern search engines ignore meta keywords. |

## 7.F — content: thin & duplicates

| Check id | Severity | Evidence | Fires on | Fix |
|---|---|---|---|---|
| `THIN_CONTENT` | warning | SF-derived | Thin content (low word count) | Add substantial, useful content or exclude the page from indexing when it has no standalone search value. |
| `LOW_TEXT_RATIO` | notice | SF-derived | Low text-to-HTML ratio | Increase the proportion of meaningful visible content or reduce unnecessary markup. |
| `DUPLICATE_BY_HASH` | warning | SF-derived | Exact duplicate content (identical hash) | Consolidate duplicates with canonicalization or rewrite them to serve distinct search intent. |
| `NEAR_DUPLICATE` | warning | SF-derived | Near-duplicate content | Differentiate the pages with substantive content or consolidate them into one canonical page. |

## 7.G — images

| Check id | Severity | Evidence | Fires on | Fix |
|---|---|---|---|---|
| `IMG_MISSING_ALT` | warning | SF:Images:Missing Alt Text | Image is missing alt text | Add concise, descriptive alt text when the image conveys content; use an empty alt attribute for decorative images. |

## 7.H — schema, hreflang, viewport

| Check id | Severity | Evidence | Fires on | Fix |
|---|---|---|---|---|
| `SCHEMA_VALIDATION_ERROR` | warning | SF:Structured Data:Validation Errors | Structured data validation errors | Correct invalid JSON-LD or Microdata markup and retest it against the applicable vocabulary and rich-result requirements. |
| `HREFLANG_ERROR` | warning | SF:Hreflang | Hreflang implementation error | Ensure hreflang annotations are reciprocal and reference canonical URLs. |

## 7.I — URL hygiene & performance

| Check id | Severity | Evidence | Fires on | Fix |
|---|---|---|---|---|
| `URL_TOO_LONG` | notice | SF-derived | URL exceeds the configured length threshold | Shorten the URL while preserving a stable, descriptive path. |
| `URL_HAS_PARAMS` | notice | SF-derived | Parameterized URL has no canonical | Point the canonical to the preferred parameter-free URL when the parameters do not create unique indexable content. |
| `URL_NON_ASCII` | notice | SF-derived | URL contains non-ASCII characters | Consider a consistent ASCII transliteration for human-readable URLs where appropriate. |
| `URL_UPPERCASE` | notice | SF-derived | URL path contains uppercase characters | Normalize the path to lowercase and add a 301 redirect from the uppercase variant. |
| `DEEP_CRAWL_DEPTH` | warning | SF-derived | Page has excessive crawl depth | Use relevant internal links to make the page reachable in fewer clicks from the home page or an authoritative hub. |
| `ORPHAN_PAGE` | warning | SF-derived | Orphan page has no internal inlinks | Add relevant internal links so users and crawlers can discover the page. |
| `SLOW_RESPONSE` | warning | SF-derived | Slow server response | Improve TTFB by profiling the application and origin, then optimizing caching and infrastructure. |
| `LARGE_HTML` | warning | SF-derived+heuristic | HTML document is large in absolute terms or relative to the site | Reduce HTML size by removing unnecessary markup, extracting inline styles or scripts, and avoiding embedded base64 assets. |

## 7.J — security

| Check id | Severity | Evidence | Fires on | Fix |
|---|---|---|---|---|
| `HTTP_URL` | warning | SF-derived | URL uses HTTP instead of HTTPS | Serve the URL over HTTPS and redirect the HTTP version with a 301. |

## 7.K — sitemap & robots

| Check id | Severity | Evidence | Fires on | Fix |
|---|---|---|---|---|
| `SITEMAP_NOT_IN_ROBOTS` | notice | sitemap | robots.txt does not declare a Sitemap directive | Add a Sitemap directive to robots.txt with the absolute sitemap URL. |
| `SITEMAP_URL_3XX` | warning | sitemap | Sitemap URL returns a 3xx response | List the final 200-status URL in the sitemap instead of a redirecting URL. |
| `SITEMAP_URL_4XX_5XX` | critical | sitemap | Sitemap URL returns a 4xx or 5xx response | Remove broken URLs from the sitemap or restore them before listing them again. |
| `SITEMAP_URL_NON_INDEXABLE` | warning | sitemap | Sitemap contains a non-indexable URL | Keep only canonical, indexable URLs in the sitemap. |
| `SITEMAP_ORPHAN` | warning | sitemap | Sitemap URL has no internal inlinks | Add relevant internal links to the page or remove it from the sitemap if it should not be discoverable. |
| `URL_NOT_IN_SITEMAP` | notice | sitemap | Indexable page is missing from the sitemap | Add the canonical page URL to the appropriate sitemap. |
| `SITEMAP_STALE_LASTMOD` | notice | sitemap | Sitemap contains stale or boilerplate lastmod values | Generate each lastmod value from the page's actual meaningful modification date. |
| `SITEMAP_DESYNC` | warning | sitemap | Sitemap and crawl URL sets are out of sync | Synchronize the sitemap with the site's actual set of canonical, indexable pages. |
| `SITEMAP_FETCH_INCOMPLETE` | notice | sitemap | Some child sitemaps could not be fetched because of network or availability errors | Check that every child sitemap is reachable and retry the audit in case the sitemap service was temporarily slow. |

## 8.x — heuristics beyond SF

| Check id | Severity | Evidence | Fires on | Fix |
|---|---|---|---|---|
| `HTML_BLOAT` | notice | heuristic | HTML bloat: high document size relative to text content | Reduce bytes per word by extracting styles and scripts, removing embedded base64 assets, and simplifying markup. |
| `DOM_TOO_DEEP` | notice | heuristic | DOM nesting is too deep | Simplify the layout hierarchy and remove unnecessary wrapper elements. |
| `DOM_TOO_MANY_NODES` | notice | heuristic | DOM contains too many nodes | Reduce the number of page elements and avoid rendering unnecessary or duplicated components. |
| `TITLE_TEMPLATED` | notice | heuristic | Templated titles share a common prefix or suffix across most pages | Make the page-specific portion of each title distinctive; a shared brand suffix is acceptable, but duplicated core title text is not. |

## --- extension: URL hygiene ---

| Check id | Severity | Evidence | Fires on | Fix |
|---|---|---|---|---|
| `URL_UNDERSCORES` | notice | SF:URL:Underscores | URL contains underscores | Use hyphens instead of underscores in URL path segments. |
| `URL_MULTIPLE_SLASHES` | notice | SF:URL:Multiple Slashes | URL path contains repeated slashes | Remove duplicate slashes and 301-redirect the malformed variant to the canonical path. |
| `URL_CONTAINS_SPACE` | warning | SF:URL:Contains Space | URL contains a space | Remove literal spaces and %20 sequences from the canonical URL structure. |
| `URL_REPETITIVE_PATH` | notice | SF:URL:Repetitive Path | URL path contains a repeated segment | Simplify the URL structure so path segments are not duplicated. |
| `URL_TRACKING_PARAMS` | warning | SF-derived | Indexable URL contains a tracking parameter such as utm_, gclid, or fbclid | Remove tracking parameters from public links; for parameterized URLs that still receive traffic, add a self-referencing canonical or manage crawling through robots.txt and Search Console as appropriate. |

## --- extension: content and readability ---

| Check id | Severity | Evidence | Fires on | Fix |
|---|---|---|---|---|
| `READABILITY_DIFFICULT` | notice | SF-derived | Text is difficult to read (low Flesch score) | Use clearer wording and shorter sentences while preserving technical accuracy. |
| `LONG_SENTENCES` | notice | SF-derived | Average sentence length is too high | Break long sentences into shorter, focused statements. |
| `SPELLING_ERRORS` | notice | SF:Content:Spelling Errors | Spelling errors detected | Review and correct spelling errors, accounting for valid product names and specialist terminology. |
| `GRAMMAR_ERRORS` | notice | SF:Content:Grammar Errors | Grammar errors detected | Review and correct the flagged grammar issues in their full sentence context. |

## --- extension: robots directives ---

| Check id | Severity | Evidence | Fires on | Fix |
|---|---|---|---|---|
| `NOARCHIVE` | notice | SF:Directives:NoArchive | Page contains a noarchive directive | Confirm that preventing cached search-result copies is intentional. |
| `NOSNIPPET` | notice | SF:Directives:NoSnippet | Page contains a nosnippet directive | Confirm that suppressing the page's search-result snippet is intentional. |
| `NOIMAGEINDEX` | notice | SF:Directives:NoImageIndex | Page contains a noimageindex directive | Confirm that preventing images on this page from being indexed is intentional. |
| `META_REFRESH_REDIRECT` | warning | SF:Directives:Refresh | Redirect is implemented with meta refresh | Replace meta refresh with a server-side 301 redirect when the move is permanent. |
| `NOTRANSLATE` | notice | SF-derived | Page contains a notranslate directive | Confirm that blocking the browser's offer-to-translate prompt is intentional. |
| `UNAVAILABLE_AFTER` | warning | SF-derived | Page carries an unavailable_after directive with a deindex date | Confirm the date is intentional and in the future; once it passes, the page is removed from the index automatically. |

## --- extension: canonicals ---

| Check id | Severity | Evidence | Fires on | Fix |
|---|---|---|---|---|
| `CANONICAL_RELATIVE` | notice | SF:Canonicals:Canonical Is Relative | Canonical URL is relative | Use an absolute URL in the canonical element. |
| `CANONICAL_MULTIPLE` | warning | SF:Canonicals:Multiple | Page declares multiple canonical URLs | Declare exactly one canonical URL for the page. |
| `CANONICAL_FRAGMENT` | notice | SF-derived | Canonical URL contains a #fragment | Drop the fragment; the server never receives it, so a canonical pointing at one is meaningless. |

## --- extension: canonical graph (Mode B, built from Internal:All) ---

| Check id | Severity | Evidence | Fires on | Fix |
|---|---|---|---|---|
| `CANONICAL_CHAIN` | warning | SF-derived | Canonical chain: the target canonicalizes to another URL (two or more steps) | Point the canonical directly to the final canonical URL in one step and break any canonical loops. |
| `CANONICAL_TO_REDIRECT` | warning | SF-derived | Canonical points to a redirecting URL (3xx) | Point the canonical to the final 200-status URL; otherwise search engines must resolve conflicting canonical signals. |
| `HREFLANG_BROKEN_TARGET` | warning | inlinks:All Hreflang | Hreflang points to a redirecting or broken URL (3xx, 4xx, or 5xx) | Update hreflang to reference the final 200-status URL; redirecting or broken targets undermine localization signals and crawling. |
| `HREFLANG_INVALID_CODE` | warning | inlinks:All Hreflang | Hreflang value is not a valid ISO 639-1 language / ISO 3166-1 region code | Use a valid language code, optionally followed by a valid region (e.g. en-GB, not en-UK). |
| `HREFLANG_MULTIPLE_ENTRIES` | warning | inlinks:All Hreflang | The same hreflang value is declared more than once on the page | Declare each language/region combination exactly once; conflicting duplicates make the annotation ambiguous. |
| `HREFLANG_MISSING_SELF_REFERENCE` | warning | inlinks:All Hreflang | Page declares hreflang alternates but does not reference itself | Every page in an hreflang set must include a self-referencing annotation for its own URL and language. |
| `HREFLANG_MISSING_XDEFAULT` | notice | inlinks:All Hreflang | Hreflang set has no x-default fallback | Add an x-default annotation to catch users whose language/region does not match any declared alternate. |
| `HREFLANG_NOT_CANONICAL` | warning | inlinks:All Hreflang | Hreflang points to a URL that is not itself the canonical version | Point hreflang annotations at each target's canonical URL, not at a duplicate that canonicalizes elsewhere. |

## --- extension: pagination ---

| Check id | Severity | Evidence | Fires on | Fix |
|---|---|---|---|---|
| `PAGINATION_NONINDEXABLE` | warning | SF-derived | Pagination page is non-indexable | Pagination pages should generally remain crawlable and indexable unless a deliberate alternative architecture is in place. |

## --- extension: links ---

| Check id | Severity | Evidence | Fires on | Fix |
|---|---|---|---|---|
| `NO_INTERNAL_OUTLINKS` | warning | SF:Links:Pages Without Internal Outlinks | Dead-end page has no internal outlinks | Add relevant internal links to help users and crawlers continue through the site. |
| `HIGH_EXTERNAL_OUTLINKS` | notice | SF:Links:Pages With High External Outlinks | Page has a high number of external outlinks | Review the links for editorial relevance, spam, and unnecessary dilution of page focus. |
| `HIGH_OUTLINKS` | notice | SF:Links:Pages With High Outlinks | Page has an excessive number of outlinks | Reduce unnecessary links to preserve clear navigation and crawl focus. |
| `GENERIC_ANCHOR_TEXT` | notice | inlinks:Anchor Text | Non-descriptive anchor text such as 'here', 'read more', or 'click here' | Replace it with meaningful anchor text that describes the destination for both search engines and screen-reader users. |

## --- extension: technical checks ---

| Check id | Severity | Evidence | Fires on | Fix |
|---|---|---|---|---|
| `HTTP1_ONLY` | notice | SF-derived | Response uses HTTP/1.x rather than HTTP/2 or newer | Enable HTTP/2 or HTTP/3 on the origin server or CDN where supported. |
| `AMPHTML_PRESENT` | notice | SF-derived | AMP version is declared | Confirm that the AMP version is still required, current, valid, and canonically linked. |

## snapshot of every id Lighthouse actually defines.

| Check id | Severity | Evidence | Fires on | Fix |
|---|---|---|---|---|
| `MISSING_CHARSET` | warning | SF-derived | No character encoding declared via Content-Type or an early <meta> tag | Declare charset in the Content-Type response header, or add a <meta charset> tag in the first 1024 bytes of the HTML. |
| `MISSING_DOCTYPE` | notice | SF-derived | Document lacks a modern <!DOCTYPE html> declaration, triggering quirks mode | Add `<!DOCTYPE html>` as the very first line of the document, with no PUBLIC or SYSTEM identifier. |
| `VIEWPORT_MISSING` | warning | SF-derived | No <meta name=viewport> tag with width or an initial-scale of at least 1 | Add `<meta name="viewport" content="width=device-width, initial-scale=1">` to the document head. |
| `NO_COMPRESSION` | notice | SF-derived | HTML response is served uncompressed above the size where gzip/br would help | Enable gzip, Brotli, or deflate compression for text responses on the origin server or CDN. |

## --- extension: export-dependent native filters (active when the export is available) ---

| Check id | Severity | Evidence | Fires on | Fix |
|---|---|---|---|---|
| `MIXED_CONTENT` | warning | SF:Security:Mixed Content | Mixed content: HTTPS page loads resources over HTTP | Serve every page resource over HTTPS and update its URL accordingly. |
| `MISSING_HSTS` | notice | SF:Security:Missing HSTS Header | HSTS header is missing | Add an appropriate Strict-Transport-Security header after confirming the entire site is HTTPS-ready. |
| `STRUCTURED_DATA_MISSING` | notice | SF:Structured Data:Missing | Structured data is missing | Add relevant, accurate Schema.org markup that reflects visible page content. |
| `OG_MISSING` | notice | SF:Social:Open Graph | og:title is missing, so social previews may not render correctly | Add og:title, og:image, and og:url; at minimum, provide og:title and og:image for a useful preview. |
| `IMG_OVER_KB` | warning | SF:Images:Over X KB | Image exceeds the configured file-size threshold | Compress the image and consider converting it to WebP or AVIF while preserving acceptable visual quality. |
| `IMG_MISSING_DIMENSIONS` | notice | SF:Images:Missing Size Attributes | Image is missing width and height attributes | Declare intrinsic width and height values to reserve layout space and reduce CLS. |
