# Check Registry (Issue Registry)

Total checks: **96**. Generated from `seohead/sf/core/registry.py`.

| ID | Severity | Source | What it means | How to fix it |
|---|---|---|---|---|
| `BROKEN_INTERNAL_LINK` | critical | inlinks:Client Error (4xx) Inlinks | An internal link points to a 4xx URL | Replace it with the current URL or add a 301 redirect; if the link is in the footer/navigation, update the template. |
| `BROKEN_PAGE_4XX` | critical | SF:Response Codes:4xx | The page returns a 4xx response (broken page) | Restore the page or add a 301 redirect to a relevant URL; remove links pointing to it. |
| `LINK_TO_5XX` | critical | inlinks:Server Error (5xx) Inlinks | An internal link points to a 5xx URL | Fix the target page or remove the link. |
| `NO_RESPONSE` | critical | SF:Response Codes:No Response | No response (timeout/DNS/connection failure) | Check host availability, DNS, and timeout settings. |
| `REDIRECT_LOOP` | critical | SF:report Redirect Chains | Redirect loop | Break the redirect loop. |
| `SERVER_ERROR_5XX` | critical | SF:Response Codes:5xx | The page returns a 5xx response (server error) | Check the server/application; the error makes the page unavailable to users and crawlers. |
| `SITEMAP_URL_4XX_5XX` | critical | sitemap | A URL in the sitemap returns 4xx/5xx | Remove broken URLs from the sitemap. |
| `TITLE_MISSING` | critical | SF-derived | The Title is missing | Add a unique, meaningful Title. |
| `BLOCKED_BY_ROBOTS` | warning | SF:Response Codes:Blocked by Robots.txt | The URL is blocked by robots.txt | Make sure the block is intentional; indexable pages should not be blocked. |
| `BROKEN_EXTERNAL_LINK` | warning | inlinks:Client Error (4xx) Inlinks | An external link points to a 4xx/5xx URL | Update or remove the broken external link (note that some sites return 403 responses to bots). |
| `CANONICAL_CHAIN` | warning | SF-derived | Canonical chain: the target is itself canonicalized further (≥2 steps) | Point the canonical directly to the final canonical URL (1 step); break any loops. |
| `CANONICAL_MISSING` | warning | SF-derived | An indexable page has no canonical | Add `<link rel=canonical>`. |
| `CANONICAL_MULTIPLE` | warning | SF:Canonicals:Multiple | The page has multiple canonicals | Keep a single canonical. |
| `CANONICAL_NON_INDEXABLE` | warning | SF-derived | The canonical points to a non-indexable URL | Canonicalize to an indexable version. |
| `CANONICAL_TO_REDIRECT` | warning | SF-derived | The canonical points to a redirecting URL (3xx) | Change the canonical to the final 200 URL; otherwise, the search engine chooses the canonical page itself. |
| `DEEP_CRAWL_DEPTH` | warning | SF-derived | High click depth | Use internal linking to move the page closer to the homepage. |
| `DESC_DUPLICATE` | warning | SF-derived | Duplicate Meta Description | Make descriptions unique. |
| `DESC_MISSING` | warning | SF-derived | The Meta Description is missing | Add a description of up to ~160 characters. |
| `DUPLICATE_BY_HASH` | warning | SF-derived | Fully identical content (same Hash) | Canonicalize or revise the duplicates. |
| `H1_MISSING` | warning | SF-derived | The H1 is missing | Add one H1 relevant to the page topic. |
| `H1_MULTIPLE` | warning | SF:H1:Multiple | The page has multiple H1s | Keep one H1; demote the others to H2/H3. |
| `HREFLANG_BROKEN_TARGET` | warning | inlinks:All Hreflang | Hreflang points to a broken or redirecting URL (3xx/4xx/5xx) | Update hreflang to the final 200 URL; broken targets disrupt localization and crawling. |
| `HREFLANG_ERROR` | warning | SF:Hreflang | Hreflang error | Make hreflang links reciprocal and canonical. |
| `HTTP_URL` | warning | SF-derived | The URL uses http:// rather than https | Migrate it to HTTPS and add a 301 redirect. |
| `IMG_MISSING_ALT` | warning | SF:Images:Missing Alt Text | An image has no alt text | Add descriptive alt text. |
| `IMG_OVER_KB` | warning | SF:Images:Over X KB | Oversized image | Compress it or convert it to WebP/AVIF. |
| `IMPORTANT_URL_BLOCKED_BY_ROBOTS` | warning | SF-derived | A live page is blocked in robots.txt but has internal links pointing to it | robots.txt blocks crawling, not indexing, so link discovery is lost. Allow the URL in robots.txt (use a more specific Allow than Disallow); control indexing with canonical/noindex. A common case is pagination such as `/blog?page=N` under `Disallow: /*?`. |
| `INTERNAL_LINK_TO_REDIRECT` | warning | inlinks:Redirection (3xx) Inlinks | An internal link points to a redirect (3xx) | Update the link to point to the final URL and remove the unnecessary hop. |
| `LARGE_HTML` | warning | SF-derived+heuristic | Oversized HTML, either in absolute terms or relative to the site | Reduce HTML size: inline styles/scripts, base64 data, and unnecessary markup. |
| `META_REFRESH_REDIRECT` | warning | SF:Directives:Refresh | Redirect implemented with meta refresh | Replace the meta refresh with a server-side 301 redirect. |
| `MIXED_CONTENT` | warning | SF:Security:Mixed Content | Mixed content: HTTP resources on an HTTPS page | Migrate the resources to HTTPS. |
| `NEAR_DUPLICATE` | warning | SF-derived | Near-duplicate content | Differentiate the pages by content or consolidate them. |
| `NO_INTERNAL_OUTLINKS` | warning | SF:Links:Pages Without Internal Outlinks | Dead-end page with no outgoing internal links | Add outgoing internal links. |
| `ORPHAN_PAGE` | warning | SF-derived | Orphan page with no internal links pointing to it | Add internal links to the page. |
| `PAGINATION_NONINDEXABLE` | warning | SF-derived | A pagination page is non-indexable | Pagination pages should generally be indexable. |
| `REDIRECT_CHAIN` | warning | SF:report Redirect Chains | Redirect chain (≥2 hops) | Shorten the chain to a single 301 redirect to the final URL. |
| `SCHEMA_VALIDATION_ERROR` | warning | SF:Structured Data:Validation Errors | Structured data errors | Fix the JSON-LD/Microdata markup. |
| `SITEMAP_DESYNC` | warning | sitemap | The sitemap and crawl are out of sync | Synchronize the sitemap with the actual set of indexable pages. |
| `SITEMAP_ORPHAN` | warning | sitemap | A URL is in the sitemap but has no internal links pointing to it | Add internal links or remove the URL from the sitemap. |
| `SITEMAP_URL_3XX` | warning | sitemap | A URL in the sitemap returns 3xx | Include only final 200 URLs in the sitemap. |
| `SITEMAP_URL_NON_INDEXABLE` | warning | sitemap | A non-indexable URL is in the sitemap | Keep only indexable URLs in the sitemap. |
| `SLOW_RESPONSE` | warning | SF-derived | Slow server response | Optimize TTFB, the server, and caching. |
| `THIN_CONTENT` | warning | SF-derived | Thin content (low word count) | Expand the content or prevent it from being indexed. |
| `TITLE_DUPLICATE` | warning | SF-derived | Duplicate Title | Make the Title unique for each page. |
| `TITLE_MULTIPLE` | warning | SF:Page Titles:Multiple | The page has multiple `<title>` tags | Keep one `<title>`. |
| `URL_CONTAINS_SPACE` | warning | SF:URL:Contains Space | The URL contains a space | Remove spaces/%20 from the URL. |
| `URL_TRACKING_PARAMS` | warning | SF-derived | The URL of an indexable page contains a tracking parameter (utm_/gclid/fbclid/…) | Remove tracking parameters from public links; to handle incoming traffic, add a self-referencing canonical or block the parameters in robots.txt/Search Console. |
| `AMPHTML_PRESENT` | notice | SF-derived | An AMP version is declared (informational) | Verify that the AMP version is current and valid. |
| `BAD_REDIRECT_TYPE` | notice | SF-derived | A temporary redirect (302/303/307) is used where a permanent redirect (301) is expected | If the move is permanent, use 301. |
| `CANONICALISED` | notice | SF-derived | The canonical points to another URL | Verify that the canonicalization is intentional. |
| `CANONICAL_RELATIVE` | notice | SF:Canonicals:Canonical Is Relative | Relative canonical | Use an absolute URL in the canonical. |
| `DESC_TOO_LONG` | notice | SF-derived | The Meta Description exceeds the threshold | Shorten the description. |
| `DESC_TOO_SHORT` | notice | SF-derived | The Meta Description is shorter than the threshold | Expand the description. |
| `DOM_TOO_DEEP` | notice | heuristic | The DOM is too deeply nested | Simplify the markup hierarchy. |
| `DOM_TOO_MANY_NODES` | notice | heuristic | The DOM has too many nodes | Reduce the number of elements on the page. |
| `EXTERNAL_LINK_TO_REDIRECT` | notice | inlinks:Redirection (3xx) Inlinks | An external link points to a redirect (3xx) | This is usually normal for external sites; optionally link directly to the final URL. |
| `GENERIC_ANCHOR_TEXT` | notice | inlinks:Anchor Text | Non-descriptive anchor text ("here"/"this"/"read more"/"click here") | Replace it with meaningful anchor text that describes the link target, for both SEO and screen readers. |
| `GRAMMAR_ERRORS` | notice | SF:Content:Grammar Errors | Grammatical errors | Correct the grammar. |
| `H1_DUPLICATE` | notice | SF-derived | The same H1 appears on different URLs | Make H1s unique. |
| `H1_TOO_LONG` | notice | SF-derived | The H1 exceeds the threshold | Shorten the H1. |
| `H2_MISSING` | notice | SF-derived | The page has an H1 but no H2 | Add H2 subheadings to provide structure. |
| `HIGH_EXTERNAL_OUTLINKS` | notice | SF:Links:Pages With High External Outlinks | Many outgoing external links | Check for link equity leakage and spam links. |
| `HIGH_OUTLINKS` | notice | SF:Links:Pages With High Outlinks | The page has a very large number of outgoing links | Reduce the number of links to focus crawling. |
| `HTML_BLOAT` | notice | heuristic | Bloated HTML: high byte size with little text | Reduce bytes per word: extract styles/scripts and remove base64 data. |
| `HTTP1_ONLY` | notice | SF-derived | Served over HTTP/1.x rather than HTTP/2 | Enable HTTP/2+ on the server/CDN. |
| `IMG_MISSING_DIMENSIONS` | notice | SF:Images:Missing Size Attributes | An image has no width/height attributes | Specify dimensions to keep the layout stable (CLS). |
| `LONG_SENTENCES` | notice | SF-derived | Sentences are too long on average | Break up long sentences. |
| `LOW_TEXT_RATIO` | notice | SF-derived | Low text-to-HTML ratio | Increase the proportion of substantive text. |
| `META_KEYWORDS_PRESENT` | notice | SF-derived | The obsolete meta keywords tag is present | It can be removed because search engines ignore it. |
| `MISSING_HSTS` | notice | SF:Security:Missing HSTS Header | The HSTS header is missing | Add Strict-Transport-Security. |
| `NOARCHIVE` | notice | SF:Directives:NoArchive | noarchive directive | Verify that disabling caching is intentional. |
| `NOFOLLOW_PAGE` | notice | SF:Directives:Nofollow | nofollow directive on the page | Check its impact on link equity flow. |
| `NOIMAGEINDEX` | notice | SF:Directives:NoImageIndex | noimageindex directive | Images on the page will not be indexed; verify that this is intentional. |
| `NOINDEX` | notice | SF:Directives:Noindex | noindex directive | Make sure exclusion from indexing is intentional. |
| `NON_INDEXABLE_LINKED` | notice | SF-derived | A non-indexable page has internal links pointing to it | Check whether the page should be indexed; otherwise, remove the internal links or account for the crawl budget. |
| `NOSNIPPET` | notice | SF:Directives:NoSnippet | nosnippet directive | nosnippet removes the search result snippet; verify that this is intentional. |
| `OG_MISSING` | notice | SF:Social:Open Graph | og:title is missing, so the social preview cannot be generated | Add og:title/og:image/og:url; at minimum, add og:title and og:image for a correct preview. |
| `READABILITY_DIFFICULT` | notice | SF-derived | Text is difficult to read (low Flesch score) | Simplify the wording and use shorter sentences. |
| `ROBOTS_BLOCKS_RESOURCES` | notice | sitemap | robots.txt blocks resources (JS/CSS), breaking rendering for crawlers | Do not block `.js`, `.css`, or `_next/static` in robots.txt; otherwise, Google renders the page incompletely. |
| `SITEMAP_FETCH_INCOMPLETE` | notice | sitemap | Some child sitemaps could not be downloaded (network/availability issue) | Check sitemap availability and retry; the sitemap may have been temporarily slow. |
| `SITEMAP_NOT_IN_ROBOTS` | notice | sitemap | robots.txt has no Sitemap: directive | Add a Sitemap: directive to robots.txt. |
| `SITEMAP_STALE_LASTMOD` | notice | sitemap | Stale or boilerplate lastmod values in the sitemap | Generate lastmod from each page's actual modification date. |
| `SPELLING_ERRORS` | notice | SF:Content:Spelling Errors | Spelling errors | Correct the spelling. |
| `STRUCTURED_DATA_MISSING` | notice | SF:Structured Data:Missing | Structured data is missing | Add relevant Schema.org markup. |
| `TITLE_EQUALS_H1` | notice | SF-derived | The Title is identical to the H1 | Differentiate the Title and H1 by meaning/keywords. |
| `TITLE_TEMPLATED` | notice | heuristic | Boilerplate Titles (most pages share a common prefix/suffix) | Vary the Titles; a shared brand suffix is normal, but identical main text is not. |
| `TITLE_TOO_LONG` | notice | SF-derived | The Title exceeds the threshold | Shorten the Title to fit the character/pixel limit. |
| `TITLE_TOO_SHORT` | notice | SF-derived | The Title is shorter than the threshold | Expand the Title to an informative length. |
| `URL_HAS_PARAMS` | notice | SF-derived | The URL has parameters but no canonical | Canonicalize to the parameter-free version. |
| `URL_MULTIPLE_SLASHES` | notice | SF:URL:Multiple Slashes | Repeated slashes in the URL path | Remove double slashes and add a 301 redirect to the canonical path. |
| `URL_NON_ASCII` | notice | SF-derived | The URL contains non-ASCII characters | Use transliteration/Latin characters for human-readable URLs. |
| `URL_NOT_IN_SITEMAP` | notice | sitemap | An indexable page is missing from the sitemap | Add the page to the sitemap. |
| `URL_REPETITIVE_PATH` | notice | SF:URL:Repetitive Path | A path segment is repeated in the URL | Simplify the URL structure by removing duplicate segments. |
| `URL_TOO_LONG` | notice | SF-derived | The URL is too long | Shorten the URL. |
| `URL_UNDERSCORES` | notice | SF:URL:Underscores | The URL contains underscores | Use hyphens instead of underscores. |
| `URL_UPPERCASE` | notice | SF-derived | The URL path contains uppercase letters | Convert the path to lowercase and add a 301 redirect. |
