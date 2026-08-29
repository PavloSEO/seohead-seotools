"""Issue registry: one row per check and the single source of truth.

Each entry carries the default severity, the data source tag, a human message
and a fix hint. The rule engine looks these up so check code stays declarative;
config can override severity/enabled per check id without touching code.
"""

from __future__ import annotations

from typing import Any

# check_id -> metadata. ``source`` uses these evidence tags:
#   SF:<tab>        native SF filter
#   SF-derived      computed from Internal:All columns
#   inlinks         from a *:Inlinks bulk export
#   heuristic       statistical / DOM heuristics
#   sitemap         robots.txt + sitemap module
CHECKS: dict[str, dict[str, Any]] = {
    # 7.A — indexing & response codes
    "BROKEN_PAGE_4XX": {
        "severity": "critical",
        "source": "SF:Response Codes:4xx",
        "message": "Page returns a 4xx response (broken page)",
        "fix": "Restore the page or redirect it with a 301 to a relevant URL; remove or update links that point to it.",
    },
    "SERVER_ERROR_5XX": {
        "severity": "critical",
        "source": "SF:Response Codes:5xx",
        "message": "Page returns a 5xx response (server error)",
        "fix": "Investigate the server or application; this error makes the page unavailable to users and crawlers.",
    },
    "NO_RESPONSE": {
        "severity": "critical",
        "source": "SF:Response Codes:No Response",
        "message": "No response (timeout, DNS, or connection failure)",
        "fix": "Check host availability, DNS resolution, connectivity, and timeout settings.",
    },
    "BLOCKED_BY_ROBOTS": {
        "severity": "warning",
        "source": "SF:Response Codes:Blocked by Robots.txt",
        "message": "URL is blocked by robots.txt",
        "fix": "Confirm that the block is intentional; pages intended for indexing should remain crawlable.",
    },
    "NON_INDEXABLE_LINKED": {
        "severity": "notice",
        "source": "SF-derived",
        "message": "Internally linked page is non-indexable",
        "fix": "Decide whether the page should be indexable; otherwise remove unnecessary internal links and account for crawl-budget impact.",
    },
    "IMPORTANT_URL_BLOCKED_BY_ROBOTS": {
        "severity": "warning",
        "source": "SF-derived",
        "message": "Live page is blocked by robots.txt despite receiving internal links",
        "fix": "robots.txt blocks crawling, not indexing, so link discovery is lost. Make the URL crawlable with a more specific Allow rule than the matching Disallow, and control indexing with canonical or noindex. A common case is pagination such as /blog?page=N blocked by Disallow: /*?.",
    },
    "ROBOTS_BLOCKS_RESOURCES": {
        "severity": "notice",
        "source": "sitemap",
        "message": "robots.txt blocks JavaScript or CSS resources required for rendering",
        "fix": "Do not block .js, .css, or _next/static resources in robots.txt; otherwise Google may render the page incompletely.",
    },
    # 7.B — links & DOM localization
    "BROKEN_INTERNAL_LINK": {
        "severity": "critical",
        "source": "inlinks:Client Error (4xx) Inlinks",
        "message": "Internal link points to a 4xx URL",
        "fix": "Update the link to the current URL or add an appropriate 301 redirect; if it appears in the footer or navigation, fix the shared template.",
    },
    "LINK_TO_5XX": {
        "severity": "critical",
        "source": "inlinks:Server Error (5xx) Inlinks",
        "message": "Internal link points to a 5xx URL",
        "fix": "Repair the destination page or remove the link.",
    },
    "INTERNAL_LINK_TO_REDIRECT": {
        "severity": "warning",
        "source": "inlinks:Redirection (3xx) Inlinks",
        "message": "Internal link points to a redirect (3xx)",
        "fix": "Point the link directly to the final URL to eliminate the unnecessary redirect hop.",
    },
    "BROKEN_EXTERNAL_LINK": {
        "severity": "warning",
        "source": "inlinks:Client Error (4xx) Inlinks",
        "message": "External link points to a 4xx or 5xx URL",
        "fix": "Update or remove the broken external link, while accounting for sites that intentionally return 403 responses to crawlers.",
    },
    "EXTERNAL_LINK_TO_REDIRECT": {
        "severity": "notice",
        "source": "inlinks:Redirection (3xx) Inlinks",
        "message": "External link points to a redirect (3xx)",
        "fix": "This is often acceptable for external sites; optionally update the link to point directly to the final URL.",
    },
    "REDIRECT_CHAIN": {
        "severity": "warning",
        "source": "SF:report Redirect Chains",
        "message": "Redirect chain contains two or more hops",
        "fix": "Replace the chain with a single 301 redirect to the final URL.",
    },
    "REDIRECT_LOOP": {
        "severity": "critical",
        "source": "SF:report Redirect Chains",
        "message": "Redirect loop detected",
        "fix": "Break the redirect cycle so every redirect path terminates at a valid destination.",
    },
    "BAD_REDIRECT_TYPE": {
        "severity": "notice",
        "source": "SF-derived",
        "message": "Temporary redirect (302 or 307) used where a permanent redirect is expected",
        "fix": "Use a 301 redirect when the move is permanent.",
    },
    # 7.C — title & meta description
    "TITLE_MISSING": {
        "severity": "critical",
        "source": "SF-derived",
        "message": "Title element is missing",
        "fix": "Add a unique, descriptive title element.",
    },
    "TITLE_DUPLICATE": {
        "severity": "warning",
        "source": "SF-derived",
        "message": "Duplicate title element",
        "fix": "Give each page a unique title element.",
    },
    "TITLE_MULTIPLE": {
        "severity": "warning",
        "source": "SF:Page Titles:Multiple",
        "message": "Multiple <title> elements",
        "fix": "Keep exactly one <title> element in the document head.",
    },
    "TITLE_TOO_LONG": {
        "severity": "notice",
        "source": "SF-derived",
        "message": "Title exceeds the configured length threshold",
        "fix": "Shorten the title to fit the configured character or pixel-width limit.",
    },
    "TITLE_TOO_SHORT": {
        "severity": "notice",
        "source": "SF-derived",
        "message": "Title falls below the configured length threshold",
        "fix": "Expand the title to an informative length without padding it with boilerplate.",
    },
    "TITLE_EQUALS_H1": {
        "severity": "notice",
        "source": "SF-derived",
        "message": "Title is identical to the H1",
        "fix": "Differentiate the title and H1 by purpose, wording, or keyword emphasis.",
    },
    "DESC_MISSING": {
        "severity": "warning",
        "source": "SF-derived",
        "message": "Meta description is missing",
        "fix": "Add a useful meta description, typically up to about 160 characters.",
    },
    "DESC_DUPLICATE": {
        "severity": "warning",
        "source": "SF-derived",
        "message": "Duplicate meta description",
        "fix": "Write a unique meta description for each page.",
    },
    "DESC_TOO_LONG": {
        "severity": "notice",
        "source": "SF-derived",
        "message": "Meta description exceeds the configured length threshold",
        "fix": "Shorten the description while preserving its primary value proposition.",
    },
    "DESC_TOO_SHORT": {
        "severity": "notice",
        "source": "SF-derived",
        "message": "Meta description falls below the configured length threshold",
        "fix": "Expand the description with specific, useful page information.",
    },
    # 7.D — headings (incl. multiple H1)
    "H1_MISSING": {
        "severity": "warning",
        "source": "SF-derived",
        "message": "H1 heading is missing",
        "fix": "Add one H1 that clearly states the page topic.",
    },
    "H1_MULTIPLE": {
        "severity": "warning",
        "source": "SF:H1:Multiple",
        "message": "Multiple H1 headings on the page",
        "fix": "Keep one primary H1 and demote the remaining headings to H2 or H3 as appropriate.",
    },
    "H1_DUPLICATE": {
        "severity": "notice",
        "source": "SF-derived",
        "message": "H1 is duplicated across multiple URLs",
        "fix": "Use a unique, page-specific H1 on each URL.",
    },
    "H1_TOO_LONG": {
        "severity": "notice",
        "source": "SF-derived",
        "message": "H1 exceeds the configured length threshold",
        "fix": "Shorten the H1 while retaining the page's main topic.",
    },
    "H2_MISSING": {
        "severity": "notice",
        "source": "SF-derived",
        "message": "Page has an H1 but no H2 headings",
        "fix": "Add meaningful H2 subheadings where needed to structure the content.",
    },
    # 7.E — canonical & directives
    "CANONICAL_MISSING": {
        "severity": "warning",
        "source": "SF-derived",
        "message": "Indexable page has no canonical URL",
        "fix": 'Add a valid <link rel="canonical"> element.',
    },
    "CANONICALISED": {
        "severity": "notice",
        "source": "SF-derived",
        "message": "Canonical points to a different URL",
        "fix": "Confirm that cross-canonicalization is intentional and that the target is the preferred version.",
    },
    "CANONICAL_NON_INDEXABLE": {
        "severity": "warning",
        "source": "SF-derived",
        "message": "Canonical points to a non-indexable URL",
        "fix": "Point the canonical to an indexable preferred version.",
    },
    "NOINDEX": {
        "severity": "notice",
        "source": "SF:Directives:Noindex",
        "message": "Page contains a noindex directive",
        "fix": "Confirm that exclusion from indexing is intentional.",
    },
    "NOFOLLOW_PAGE": {
        "severity": "notice",
        "source": "SF:Directives:Nofollow",
        "message": "Page-level nofollow directive is present",
        "fix": "Confirm the directive is intentional and review its effect on crawling and internal link equity.",
    },
    "META_KEYWORDS_PRESENT": {
        "severity": "notice",
        "source": "SF-derived",
        "message": "Obsolete meta keywords element is present",
        "fix": "Remove it if desired; modern search engines ignore meta keywords.",
    },
    # 7.F — content: thin & duplicates
    "THIN_CONTENT": {
        "severity": "warning",
        "source": "SF-derived",
        "message": "Thin content (low word count)",
        "fix": "Add substantial, useful content or exclude the page from indexing when it has no standalone search value.",
    },
    "LOW_TEXT_RATIO": {
        "severity": "notice",
        "source": "SF-derived",
        "message": "Low text-to-HTML ratio",
        "fix": "Increase the proportion of meaningful visible content or reduce unnecessary markup.",
    },
    "DUPLICATE_BY_HASH": {
        "severity": "warning",
        "source": "SF-derived",
        "message": "Exact duplicate content (identical hash)",
        "fix": "Consolidate duplicates with canonicalization or rewrite them to serve distinct search intent.",
    },
    "NEAR_DUPLICATE": {
        "severity": "warning",
        "source": "SF-derived",
        "message": "Near-duplicate content",
        "fix": "Differentiate the pages with substantive content or consolidate them into one canonical page.",
    },
    # 7.G — images
    "IMG_MISSING_ALT": {
        "severity": "warning",
        "source": "SF:Images:Missing Alt Text",
        "message": "Image is missing alt text",
        "fix": "Add concise, descriptive alt text when the image conveys content; use an empty alt attribute for decorative images.",
    },
    # 7.H — schema, hreflang, viewport
    "SCHEMA_VALIDATION_ERROR": {
        "severity": "warning",
        "source": "SF:Structured Data:Validation Errors",
        "message": "Structured data validation errors",
        "fix": "Correct invalid JSON-LD or Microdata markup and retest it against the applicable vocabulary and rich-result requirements.",
    },
    "HREFLANG_ERROR": {
        "severity": "warning",
        "source": "SF:Hreflang",
        "message": "Hreflang implementation error",
        "fix": "Ensure hreflang annotations are reciprocal and reference canonical URLs.",
    },
    # 7.I — URL hygiene & performance
    "URL_TOO_LONG": {
        "severity": "notice",
        "source": "SF-derived",
        "message": "URL exceeds the configured length threshold",
        "fix": "Shorten the URL while preserving a stable, descriptive path.",
    },
    "URL_HAS_PARAMS": {
        "severity": "notice",
        "source": "SF-derived",
        "message": "Parameterized URL has no canonical",
        "fix": "Point the canonical to the preferred parameter-free URL when the parameters do not create unique indexable content.",
    },
    "URL_NON_ASCII": {
        "severity": "notice",
        "source": "SF-derived",
        "message": "URL contains non-ASCII characters",
        "fix": "Consider a consistent ASCII transliteration for human-readable URLs where appropriate.",
    },
    "URL_UPPERCASE": {
        "severity": "notice",
        "source": "SF-derived",
        "message": "URL path contains uppercase characters",
        "fix": "Normalize the path to lowercase and add a 301 redirect from the uppercase variant.",
    },
    "DEEP_CRAWL_DEPTH": {
        "severity": "warning",
        "source": "SF-derived",
        "message": "Page has excessive crawl depth",
        "fix": "Use relevant internal links to make the page reachable in fewer clicks from the home page or an authoritative hub.",
    },
    "ORPHAN_PAGE": {
        "severity": "warning",
        "source": "SF-derived",
        "message": "Orphan page has no internal inlinks",
        "fix": "Add relevant internal links so users and crawlers can discover the page.",
    },
    "SLOW_RESPONSE": {
        "severity": "warning",
        "source": "SF-derived",
        "message": "Slow server response",
        "fix": "Improve TTFB by profiling the application and origin, then optimizing caching and infrastructure.",
    },
    "LARGE_HTML": {
        "severity": "warning",
        "source": "SF-derived+heuristic",
        "message": "HTML document is large in absolute terms or relative to the site",
        "fix": "Reduce HTML size by removing unnecessary markup, extracting inline styles or scripts, and avoiding embedded base64 assets.",
    },
    # 7.J — security
    "HTTP_URL": {
        "severity": "warning",
        "source": "SF-derived",
        "message": "URL uses HTTP instead of HTTPS",
        "fix": "Serve the URL over HTTPS and redirect the HTTP version with a 301.",
    },
    # 7.K — sitemap & robots
    "SITEMAP_NOT_IN_ROBOTS": {
        "severity": "notice",
        "source": "sitemap",
        "message": "robots.txt does not declare a Sitemap directive",
        "fix": "Add a Sitemap directive to robots.txt with the absolute sitemap URL.",
    },
    "SITEMAP_URL_3XX": {
        "severity": "warning",
        "source": "sitemap",
        "message": "Sitemap URL returns a 3xx response",
        "fix": "List the final 200-status URL in the sitemap instead of a redirecting URL.",
    },
    "SITEMAP_URL_4XX_5XX": {
        "severity": "critical",
        "source": "sitemap",
        "message": "Sitemap URL returns a 4xx or 5xx response",
        "fix": "Remove broken URLs from the sitemap or restore them before listing them again.",
    },
    "SITEMAP_URL_NON_INDEXABLE": {
        "severity": "warning",
        "source": "sitemap",
        "message": "Sitemap contains a non-indexable URL",
        "fix": "Keep only canonical, indexable URLs in the sitemap.",
    },
    "SITEMAP_ORPHAN": {
        "severity": "warning",
        "source": "sitemap",
        "message": "Sitemap URL has no internal inlinks",
        "fix": "Add relevant internal links to the page or remove it from the sitemap if it should not be discoverable.",
    },
    "URL_NOT_IN_SITEMAP": {
        "severity": "notice",
        "source": "sitemap",
        "message": "Indexable page is missing from the sitemap",
        "fix": "Add the canonical page URL to the appropriate sitemap.",
    },
    "SITEMAP_STALE_LASTMOD": {
        "severity": "notice",
        "source": "sitemap",
        "message": "Sitemap contains stale or boilerplate lastmod values",
        "fix": "Generate each lastmod value from the page's actual meaningful modification date.",
    },
    "SITEMAP_DESYNC": {
        "severity": "warning",
        "source": "sitemap",
        "message": "Sitemap and crawl URL sets are out of sync",
        "fix": "Synchronize the sitemap with the site's actual set of canonical, indexable pages.",
    },
    "SITEMAP_FETCH_INCOMPLETE": {
        "severity": "notice",
        "source": "sitemap",
        "message": "Some child sitemaps could not be fetched because of network or availability errors",
        "fix": "Check that every child sitemap is reachable and retry the audit in case the sitemap service was temporarily slow.",
    },
    # 8.x — heuristics beyond SF
    "HTML_BLOAT": {
        "severity": "notice",
        "source": "heuristic",
        "message": "HTML bloat: high document size relative to text content",
        "fix": "Reduce bytes per word by extracting styles and scripts, removing embedded base64 assets, and simplifying markup.",
    },
    "DOM_TOO_DEEP": {
        "severity": "notice",
        "source": "heuristic",
        "message": "DOM nesting is too deep",
        "fix": "Simplify the layout hierarchy and remove unnecessary wrapper elements.",
    },
    "DOM_TOO_MANY_NODES": {
        "severity": "notice",
        "source": "heuristic",
        "message": "DOM contains too many nodes",
        "fix": "Reduce the number of page elements and avoid rendering unnecessary or duplicated components.",
    },
    "TITLE_TEMPLATED": {
        "severity": "notice",
        "source": "heuristic",
        "message": "Templated titles share a common prefix or suffix across most pages",
        "fix": "Make the page-specific portion of each title distinctive; a shared brand suffix is acceptable, but duplicated core title text is not.",
    },
    # --- extension: URL hygiene ---
    "URL_UNDERSCORES": {
        "severity": "notice",
        "source": "SF:URL:Underscores",
        "message": "URL contains underscores",
        "fix": "Use hyphens instead of underscores in URL path segments.",
    },
    "URL_MULTIPLE_SLASHES": {
        "severity": "notice",
        "source": "SF:URL:Multiple Slashes",
        "message": "URL path contains repeated slashes",
        "fix": "Remove duplicate slashes and 301-redirect the malformed variant to the canonical path.",
    },
    "URL_CONTAINS_SPACE": {
        "severity": "warning",
        "source": "SF:URL:Contains Space",
        "message": "URL contains a space",
        "fix": "Remove literal spaces and %20 sequences from the canonical URL structure.",
    },
    "URL_REPETITIVE_PATH": {
        "severity": "notice",
        "source": "SF:URL:Repetitive Path",
        "message": "URL path contains a repeated segment",
        "fix": "Simplify the URL structure so path segments are not duplicated.",
    },
    "URL_TRACKING_PARAMS": {
        "severity": "warning",
        "source": "SF-derived",
        "message": "Indexable URL contains a tracking parameter such as utm_, gclid, or fbclid",
        "fix": "Remove tracking parameters from public links; for parameterized URLs that still receive traffic, add a self-referencing canonical or manage crawling through robots.txt and Search Console as appropriate.",
    },
    # --- extension: content and readability ---
    "READABILITY_DIFFICULT": {
        "severity": "notice",
        "source": "SF-derived",
        "message": "Text is difficult to read (low Flesch score)",
        "fix": "Use clearer wording and shorter sentences while preserving technical accuracy.",
    },
    "LONG_SENTENCES": {
        "severity": "notice",
        "source": "SF-derived",
        "message": "Average sentence length is too high",
        "fix": "Break long sentences into shorter, focused statements.",
    },
    "SPELLING_ERRORS": {
        "severity": "notice",
        "source": "SF:Content:Spelling Errors",
        "message": "Spelling errors detected",
        "fix": "Review and correct spelling errors, accounting for valid product names and specialist terminology.",
    },
    "GRAMMAR_ERRORS": {
        "severity": "notice",
        "source": "SF:Content:Grammar Errors",
        "message": "Grammar errors detected",
        "fix": "Review and correct the flagged grammar issues in their full sentence context.",
    },
    # --- extension: robots directives ---
    "NOARCHIVE": {
        "severity": "notice",
        "source": "SF:Directives:NoArchive",
        "message": "Page contains a noarchive directive",
        "fix": "Confirm that preventing cached search-result copies is intentional.",
    },
    "NOSNIPPET": {
        "severity": "notice",
        "source": "SF:Directives:NoSnippet",
        "message": "Page contains a nosnippet directive",
        "fix": "Confirm that suppressing the page's search-result snippet is intentional.",
    },
    "NOIMAGEINDEX": {
        "severity": "notice",
        "source": "SF:Directives:NoImageIndex",
        "message": "Page contains a noimageindex directive",
        "fix": "Confirm that preventing images on this page from being indexed is intentional.",
    },
    "META_REFRESH_REDIRECT": {
        "severity": "warning",
        "source": "SF:Directives:Refresh",
        "message": "Redirect is implemented with meta refresh",
        "fix": "Replace meta refresh with a server-side 301 redirect when the move is permanent.",
    },
    # --- extension: canonicals ---
    "CANONICAL_RELATIVE": {
        "severity": "notice",
        "source": "SF:Canonicals:Canonical Is Relative",
        "message": "Canonical URL is relative",
        "fix": "Use an absolute URL in the canonical element.",
    },
    "CANONICAL_MULTIPLE": {
        "severity": "warning",
        "source": "SF:Canonicals:Multiple",
        "message": "Page declares multiple canonical URLs",
        "fix": "Declare exactly one canonical URL for the page.",
    },
    # --- extension: canonical graph (Mode B, built from Internal:All) ---
    "CANONICAL_CHAIN": {
        "severity": "warning",
        "source": "SF-derived",
        "message": "Canonical chain: the target canonicalizes to another URL (two or more steps)",
        "fix": "Point the canonical directly to the final canonical URL in one step and break any canonical loops.",
    },
    "CANONICAL_TO_REDIRECT": {
        "severity": "warning",
        "source": "SF-derived",
        "message": "Canonical points to a redirecting URL (3xx)",
        "fix": "Point the canonical to the final 200-status URL; otherwise search engines must resolve conflicting canonical signals.",
    },
    "HREFLANG_BROKEN_TARGET": {
        "severity": "warning",
        "source": "inlinks:All Hreflang",
        "message": "Hreflang points to a redirecting or broken URL (3xx, 4xx, or 5xx)",
        "fix": "Update hreflang to reference the final 200-status URL; redirecting or broken targets undermine localization signals and crawling.",
    },
    # --- extension: pagination ---
    "PAGINATION_NONINDEXABLE": {
        "severity": "warning",
        "source": "SF-derived",
        "message": "Pagination page is non-indexable",
        "fix": "Pagination pages should generally remain crawlable and indexable unless a deliberate alternative architecture is in place.",
    },
    # --- extension: links ---
    "NO_INTERNAL_OUTLINKS": {
        "severity": "warning",
        "source": "SF:Links:Pages Without Internal Outlinks",
        "message": "Dead-end page has no internal outlinks",
        "fix": "Add relevant internal links to help users and crawlers continue through the site.",
    },
    "HIGH_EXTERNAL_OUTLINKS": {
        "severity": "notice",
        "source": "SF:Links:Pages With High External Outlinks",
        "message": "Page has a high number of external outlinks",
        "fix": "Review the links for editorial relevance, spam, and unnecessary dilution of page focus.",
    },
    "HIGH_OUTLINKS": {
        "severity": "notice",
        "source": "SF:Links:Pages With High Outlinks",
        "message": "Page has an excessive number of outlinks",
        "fix": "Reduce unnecessary links to preserve clear navigation and crawl focus.",
    },
    "GENERIC_ANCHOR_TEXT": {
        "severity": "notice",
        "source": "inlinks:Anchor Text",
        "message": "Non-descriptive anchor text such as 'here', 'read more', or 'click here'",
        "fix": "Replace it with meaningful anchor text that describes the destination for both search engines and screen-reader users.",
    },
    # --- extension: technical checks ---
    "HTTP1_ONLY": {
        "severity": "notice",
        "source": "SF-derived",
        "message": "Response uses HTTP/1.x rather than HTTP/2 or newer",
        "fix": "Enable HTTP/2 or HTTP/3 on the origin server or CDN where supported.",
    },
    "AMPHTML_PRESENT": {
        "severity": "notice",
        "source": "SF-derived",
        "message": "AMP version is declared",
        "fix": "Confirm that the AMP version is still required, current, valid, and canonically linked.",
    },
    # --- extension: export-dependent native filters (active when the export is available) ---
    "MIXED_CONTENT": {
        "severity": "warning",
        "source": "SF:Security:Mixed Content",
        "message": "Mixed content: HTTPS page loads resources over HTTP",
        "fix": "Serve every page resource over HTTPS and update its URL accordingly.",
    },
    "MISSING_HSTS": {
        "severity": "notice",
        "source": "SF:Security:Missing HSTS Header",
        "message": "HSTS header is missing",
        "fix": "Add an appropriate Strict-Transport-Security header after confirming the entire site is HTTPS-ready.",
    },
    "STRUCTURED_DATA_MISSING": {
        "severity": "notice",
        "source": "SF:Structured Data:Missing",
        "message": "Structured data is missing",
        "fix": "Add relevant, accurate Schema.org markup that reflects visible page content.",
    },
    "OG_MISSING": {
        "severity": "notice",
        "source": "SF:Social:Open Graph",
        "message": "og:title is missing, so social previews may not render correctly",
        "fix": "Add og:title, og:image, and og:url; at minimum, provide og:title and og:image for a useful preview.",
    },
    "IMG_OVER_KB": {
        "severity": "warning",
        "source": "SF:Images:Over X KB",
        "message": "Image exceeds the configured file-size threshold",
        "fix": "Compress the image and consider converting it to WebP or AVIF while preserving acceptable visual quality.",
    },
    "IMG_MISSING_DIMENSIONS": {
        "severity": "notice",
        "source": "SF:Images:Missing Size Attributes",
        "message": "Image is missing width and height attributes",
        "fix": "Declare intrinsic width and height values to reserve layout space and reduce CLS.",
    },
}


def check_meta(check_id: str) -> dict[str, Any]:
    return CHECKS.get(
        check_id, {"severity": "notice", "source": "SF-derived", "message": check_id, "fix": None}
    )
