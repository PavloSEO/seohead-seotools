"""Where this toolkit stands against the field's published issue catalogue.

Screaming Frog publishes a list of the issues its crawler reports — 320 across 24 categories.
It is the closest thing technical SEO has to a shared checklist, so it is the honest yardstick
for "what does this find". Without it, "118 checks" is a number with nothing to compare to.

**Only the issue names are used here.** They are the field's shared vocabulary for these
problems — "Redirect Chain", "Missing Alt Text", "Orphan URLs" — and naming a problem is not
copying a description of it. Every explanation in this module is written about *our own*
behaviour: what we find, what we find only partly, what we do not find, and what we have
decided not to find. Nothing is reproduced from that page.

Each entry carries exactly one status:

``check``         a registry check finds it; ``refs`` names the check ids.
``tool``          a command outside the crawl registry finds it; ``refs`` names the commands.
``partial``       we find part of it. ``note`` says which part we miss.
``gap``           we should find it and do not. ``note`` says what is missing.
``out_of_scope``  we will not, and ``note`` says why it is a decision rather than an oversight.

``tests/test_sf_issue_map.py`` asserts every referenced check id and command still exists, so a
rename breaks the build instead of quietly making this document wrong.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["CATEGORIES", "Entry", "coverage_counts", "entries"]

STATUSES = ("check", "tool", "partial", "gap", "out_of_scope")


@dataclass(frozen=True)
class Entry:
    name: str
    status: str
    refs: tuple[str, ...] = ()
    note: str = ""


def _c(name: str, *refs: str, note: str = "") -> Entry:
    return Entry(name, "check", tuple(refs), note)


def _t(name: str, *refs: str, note: str = "") -> Entry:
    return Entry(name, "tool", tuple(refs), note)


def _p(name: str, note: str, *refs: str) -> Entry:
    return Entry(name, "partial", tuple(refs), note)


def _g(name: str, note: str) -> Entry:
    return Entry(name, "gap", (), note)


def _o(name: str, note: str) -> Entry:
    return Entry(name, "out_of_scope", (), note)


CATEGORIES: dict[str, list[Entry]] = {
    "Response Codes": [
        _c("Internal No Response", "NO_RESPONSE"),
        _c("Internal Client Error (4XX)", "BROKEN_PAGE_4XX", "BROKEN_INTERNAL_LINK"),
        _c("Internal Server Error (5XX)", "SERVER_ERROR_5XX", "LINK_TO_5XX"),
        _c("Internal Redirect Loop", "REDIRECT_LOOP"),
        _c(
            "Internal Blocked by Robots.txt", "BLOCKED_BY_ROBOTS", "IMPORTANT_URL_BLOCKED_BY_ROBOTS"
        ),
        _c("Internal Blocked Resource", "ROBOTS_BLOCKS_RESOURCES"),
        _c("Internal Redirect Chain", "REDIRECT_CHAIN"),
        _p(
            "External Blocked Resource",
            "we do not fetch another host's robots.txt: a crawler that goes and asks somebody "
            "else's server about its own rules is a crawler that wanders",
        ),
        _c("Internal Redirection (3XX)", "INTERNAL_LINK_TO_REDIRECT", "BAD_REDIRECT_TYPE"),
        _c("Internal Redirection (Meta Refresh)", "META_REFRESH_REDIRECT"),
        _g(
            "Internal Redirection (HTTP Refresh)",
            "the Refresh response header is not read; only the meta element is",
        ),
        _g(
            "Internal Redirection (JavaScript)",
            "needs rendering plus navigation tracking; render mode reports the DOM, not "
            "location changes",
        ),
        _t("External No Response", "links-check"),
        _c("External Client Error (4XX)", "BROKEN_EXTERNAL_LINK"),
        _c("External Server Error (5XX)", "BROKEN_EXTERNAL_LINK"),
    ],
    "Security": [
        _c("HTTP URLs", "HTTP_URL"),
        _c("Mixed Content", "MIXED_CONTENT", "INSECURE_SUBRESOURCE"),
        _g("Form URL Insecure", "form action attributes are not extracted during the crawl"),
        _g("Form On HTTP URL", "same: forms are not part of the parsed record"),
        _c("Missing HSTS Header", "MISSING_HSTS"),
        _g(
            "Unsafe Cross Origin Links",
            "target=_blank without rel=noopener is not checked; the link record has no rel "
            "beyond nofollow",
        ),
        _g("Protocol-Relative Resource Links", "// resource URLs are resolved before recording"),
        _t("Missing Content-Security-Policy Header", "security-check"),
        _t("Missing X-Content-Type-Options Header", "security-check"),
        _t("Missing X-Frames-Options Header", "security-check"),
        _t("Missing Secure Referrer-Policy Header", "security-check"),
        _p(
            "Bad Content Type",
            "content type is recorded and drives HTML detection, but a mismatch between the "
            "declared type and the body is not asserted",
        ),
    ],
    "URL": [
        _c("Multiple Slashes", "URL_MULTIPLE_SLASHES"),
        _c("Contains A Space", "URL_CONTAINS_SPACE"),
        _g("Broken Bookmark", "fragment targets are not resolved against the destination page"),
        _c("Non ASCII Characters", "URL_NON_ASCII"),
        _c("Uppercase", "URL_UPPERCASE"),
        _c("Repetitive Path", "URL_REPETITIVE_PATH"),
        _p(
            "Internal Search",
            "search URLs are caught only when they carry parameters; a path-based search route "
            "is not recognised",
            "URL_HAS_PARAMS",
        ),
        _c("Parameters", "URL_HAS_PARAMS"),
        _c("GA Tracking Parameters", "URL_TRACKING_PARAMS"),
        _c("Underscores", "URL_UNDERSCORES"),
        _c("Over 115 Characters", "URL_TOO_LONG"),
    ],
    "Page Titles": [
        _c("Missing", "TITLE_MISSING"),
        _c("Multiple", "TITLE_MULTIPLE"),
        _g("Outside <head>", "element position within the document is not recorded"),
        _c("Duplicate", "TITLE_DUPLICATE"),
        _c("Over 60 Characters", "TITLE_TOO_LONG"),
        _c("Below 30 Characters", "TITLE_TOO_SHORT"),
        _p(
            "Over 561 Pixels",
            "pixel width needs font metrics; the column is carried from an SF export when one "
            "supplies it, and is never computed here",
        ),
        _p("Below 200 Pixels", "same: pixel width is read, never computed"),
        _c("Same as H1", "TITLE_EQUALS_H1"),
    ],
    "Meta Description": [
        _g("Multiple", "only the first meta description is kept during parsing"),
        _g("Outside <head>", "element position within the document is not recorded"),
        _c("Missing", "DESC_MISSING"),
        _c("Duplicate", "DESC_DUPLICATE"),
        _c("Over 155 Characters", "DESC_TOO_LONG"),
        _c("Below 70 Characters", "DESC_TOO_SHORT"),
        _p("Over 985 Pixels", "pixel width is read from an export, never computed"),
        _p("Below 400 Pixels", "pixel width is read from an export, never computed"),
    ],
    "H1": [
        _c("Missing", "H1_MISSING"),
        _c("Multiple", "H1_MULTIPLE"),
        _g("Alt Text in h1", "an H1 whose only text comes from an image alt is not detected"),
        _t(
            "Non-sequential",
            "heading-outline",
            note="the full H1-H6 order is built by the heading-outline skill, not by the "
            "crawl registry",
        ),
        _c("Duplicate", "H1_DUPLICATE"),
        _c("Over 70 Characters", "H1_TOO_LONG"),
    ],
    "H2": [
        _c("Missing", "H2_MISSING"),
        _p("Multiple", "multiple H2s are normal; we record them without judging the count"),
        _t("Non-sequential", "heading-outline"),
        _g("Duplicate", "H2 duplication across the site is not aggregated"),
        _g("Over 70 Characters", "no length threshold is applied to H2"),
    ],
    "Content": [
        _c("Exact Duplicates", "DUPLICATE_BY_HASH"),
        _c("Spelling Errors", "SPELLING_ERRORS", note="from an SF export column; not computed"),
        _c("Grammar Errors", "GRAMMAR_ERRORS", note="from an SF export column; not computed"),
        _t("Soft 404 Pages", "soft404-check"),
        _g("Lorem Ipsum Placeholder", "no placeholder-text detection"),
        _c("Near Duplicates", "NEAR_DUPLICATE"),
        _g(
            "Semantically Similar",
            "needs embeddings; simhash finds near-duplicates by shingles, not by meaning",
        ),
        _g("Low Relevance Content", "needs a query or a topic model to be relevant to"),
        _c("Low Content Pages", "THIN_CONTENT", "LOW_TEXT_RATIO"),
        _c("Readability Difficult", "READABILITY_DIFFICULT", "LONG_SENTENCES"),
        _c("Readability Very Difficult", "READABILITY_DIFFICULT"),
    ],
    "Images": [
        _c("Missing Alt Text", "IMG_MISSING_ALT"),
        _p(
            "Missing Alt Attribute",
            "an absent attribute and an empty one are reported together; a decorative image "
            'with alt="" is correct and is not distinguished',
            "IMG_MISSING_ALT",
        ),
        _t(
            "Background Images",
            "parse",
            note="CSS url() sources are extracted by the parser's url_sources option, which is "
            "how four images invisible to the HTML were found on a live site",
        ),
        _c("Over 100 kb", "IMG_OVER_KB"),
        _g("Alt Text Over 100 Characters", "alt length is not thresholded"),
        _g(
            "Incorrectly Sized Images",
            "needs the rendered layout box to compare against the intrinsic size",
        ),
        _c("Missing Size Attributes", "IMG_MISSING_DIMENSIONS"),
    ],
    "Canonicals": [
        _c("Multiple Conflicting", "CANONICAL_MULTIPLE"),
        _c("Non-Indexable Canonical", "CANONICAL_NON_INDEXABLE"),
        _g("Invalid Attribute In Annotation", "rel attribute values are not validated"),
        _c("Contains Fragment URL", "CANONICAL_FRAGMENT"),
        _g("Outside <head>", "element position within the document is not recorded"),
        _c("Canonicalised", "CANONICALISED"),
        _c("Missing", "CANONICAL_MISSING"),
        _c("Unlinked", "UNLINKED_CANONICAL"),
        _c("Multiple", "CANONICAL_MULTIPLE"),
        _c("Canonical Is Relative", "CANONICAL_RELATIVE"),
    ],
    "Pagination": [
        _g(
            "Pagination URL Not In Anchor Tag",
            "rel=next/prev targets are not cross-checked against the anchor list",
        ),
        _c("Non-200 Pagination URLs", "PAGINATION_NONINDEXABLE"),
        _c("Unlinked Pagination URLs", "UNLINKED_PAGINATION_SERIES"),
        _g("Multiple Pagination URLs", "multiple rel=next declarations are not counted"),
        _c("Pagination Loop", "PAGINATION_LOOP"),
        _g("Sequence Error", "the numeric order of a series is not validated"),
        _c("Non-Indexable", "PAGINATION_NONINDEXABLE"),
    ],
    "Directives": [
        _g("Outside <head>", "element position within the document is not recorded"),
        _c("NoImageIndex", "NOIMAGEINDEX"),
        _c("Noindex", "NOINDEX"),
        _c("Nofollow", "NOFOLLOW_PAGE"),
        _c(
            "None",
            "NOINDEX",
            "NOFOLLOW_PAGE",
            note="'none' is expanded to noindex+nofollow when directives are parsed",
        ),
        _c("Unavailable_After", "UNAVAILABLE_AFTER"),
        _c("NoSnippet", "NOSNIPPET"),
        _o("NoODP", "the directive was retired with the Open Directory Project in 2017"),
        _o("NoYDIR", "the directive was retired with the Yahoo Directory"),
        _c("NoTranslate", "NOTRANSLATE"),
    ],
    "Hreflang": [
        _c("Non-200 Hreflang URLs", "HREFLANG_BROKEN_TARGET"),
        _c("Missing Return Links", "HREFLANG_MISSING_RETURN_LINK"),
        _p(
            "Inconsistent Language & Region Confirmation Links",
            "a return link is checked for existence, not for declaring the same locale back",
            "HREFLANG_MISSING_RETURN_LINK",
        ),
        _c("Non-Canonical Return Links", "HREFLANG_NOT_CANONICAL"),
        _g("Noindex Returns Links", "the indexability of an hreflang target is not cross-checked"),
        _c("Incorrect Language & Region Codes", "HREFLANG_INVALID_CODE"),
        _c("Multiple Entries", "HREFLANG_MULTIPLE_ENTRIES"),
        _c("Not Using Canonical", "HREFLANG_NOT_CANONICAL"),
        _g("Outside <head>", "element position within the document is not recorded"),
        _g("Unlinked Hreflang URLs", "hreflang targets are not tested against the link graph"),
        _c("Missing Self Reference", "HREFLANG_MISSING_SELF_REFERENCE"),
        _c("Missing X-Default", "HREFLANG_MISSING_XDEFAULT"),
    ],
    "JavaScript": [
        _t("Noindex Only in Original HTML", "render-check"),
        _t("Nofollow Only in Original HTML", "render-check"),
        _t("Canonical Mismatch", "render-check"),
        _p(
            "Uses Old AJAX Crawling Scheme URLs",
            "the scheme is honoured as a crawl mode (rendering.mode=legacy_fragment) but its "
            "presence is not reported as a finding",
        ),
        _p(
            "Uses Old AJAX Crawling Scheme Meta Fragment Tag",
            "the meta fragment opt-in is read to decide the mode, not reported",
        ),
        _c("Pages with Blocked Resources", "ROBOTS_BLOCKS_RESOURCES"),
        _t("Contains JavaScript Links", "render-check"),
        _t("Contains JavaScript Content", "render-check"),
        _t("Page Title Only in Rendered HTML", "render-check"),
        _t("Page Title Updated by JavaScript", "render-check"),
        _t("Meta Description Only in Rendered HTML", "render-check"),
        _t("Meta Description Updated by JavaScript", "render-check"),
        _t("H1 Only in Rendered HTML", "render-check"),
        _t("H1 Updated by JavaScript", "render-check"),
        _t("Canonical Only in Rendered HTML", "render-check"),
        _t(
            "Pages With JavaScript Errors",
            "crawl-site",
            note="browser console errors are captured per URL when "
            "rendering.artifacts.console_errors is on",
        ),
    ],
    "Links": [
        _g("Outlinks To Localhost", "a localhost destination is treated as any other off-host URL"),
        _p(
            "Pages With Uncrawlable Internal Outlinks",
            "excluded destinations are counted by reason in the run's excluded map, but not "
            "attributed back to the pages that linked them",
        ),
        _c("Pages Without Internal Outlinks", "NO_INTERNAL_OUTLINKS"),
        _c("Non-Indexable Page Inlinks Only", "ONLY_NONINDEXABLE_SOURCE_INLINKS"),
        _p(
            "Internal Nofollow Outlinks",
            "nofollow is recorded per edge and gates crawling; there is no page-level finding "
            "for having them",
        ),
        _c("Pages With High External Outlinks", "HIGH_EXTERNAL_OUTLINKS"),
        _c("Pages With High Internal Outlinks", "HIGH_OUTLINKS"),
        _g(
            "Follow & Nofollow Internal Inlinks To Page",
            "a page linked both ways from different sources is not called out",
        ),
        _c("Internal Nofollow Inlinks Only", "ONLY_NOFOLLOW_INLINKS"),
        _c("Pages With High Crawl Depth", "DEEP_CRAWL_DEPTH", "DEEP_DISCOVERY_PATH"),
        _p(
            "Internal Outlinks With No Anchor Text",
            "empty anchors are recorded; the generic-anchor check covers the wording, not the "
            "absence",
            "GENERIC_ANCHOR_TEXT",
        ),
        _c("Non-Descriptive Anchor Text In Internal Outlinks", "GENERIC_ANCHOR_TEXT"),
    ],
    "Structured Data": [
        _c("Validation Errors", "SCHEMA_VALIDATION_ERROR"),
        _t("Rich Result Validation Errors", "schema-check"),
        _p(
            "Parse Errors",
            "found and parsed block counts are recorded per page, so a malformed block is "
            "visible; it is not raised as its own registry finding",
        ),
        _c("Missing", "STRUCTURED_DATA_MISSING"),
        _t("Validation Warnings", "schema-check"),
        _t("Rich Result Validation Warnings", "schema-check"),
    ],
    "Sitemaps": [
        _g("XML Sitemap With Over 50k URLs", "the 50,000-URL protocol limit is not asserted"),
        _g("XML Sitemap Over 50mb", "the 50 MB protocol limit is not asserted"),
        _c("URLs Not In Sitemap", "URL_NOT_IN_SITEMAP"),
        _c("Orphan URLs", "SITEMAP_ORPHAN", "ORPHAN_PAGE"),
        _c("Non-Indexable URLs In Sitemap", "SITEMAP_URL_NON_INDEXABLE"),
        _g("URLs In Multiple Sitemaps", "duplicates across child sitemaps are counted, not named"),
    ],
    "PageSpeed": [
        _c("Document Request Latency", "SLOW_RESPONSE"),
        _o("LCP Request Discovery", "needs Lighthouse's own trace of the loading sequence"),
        _t("Render Blocking Requests", "asset-weight-check"),
        _o("Network Dependency Tree", "needs a full request waterfall from a real navigation"),
        _t("Use Efficient Cache Lifetimes", "headers-check", "cdn-check"),
        _o("Layout Shift Culprits", "needs layout instrumentation during a real render"),
        _t("Improve Image Delivery", "images-optimize", "asset-weight-check"),
        _o("Forced Reflow", "needs main-thread instrumentation"),
        _t("Legacy JavaScript", "asset-weight-check"),
        _t("Duplicated JavaScript", "asset-weight-check", note="by content hash across the page"),
        _c("Avoid Enormous Network Payloads", "LARGE_HTML", "HTML_BLOAT"),
        _t("Minify CSS", "asset-weight-check"),
        _t("Minify JavaScript", "asset-weight-check"),
        _o("Reduce Unused CSS", "needs coverage instrumentation from a real render"),
        _o("Reduce Unused JavaScript", "needs coverage instrumentation from a real render"),
        _o("Reduce JavaScript Execution Time", "needs a CPU profile"),
        _o("Minimize Main-Thread Work", "needs a CPU profile"),
        _c("Optimize DOM Size", "DOM_TOO_MANY_NODES", "DOM_TOO_DEEP"),
        _t("Font Display", "asset-weight-check"),
    ],
    "Mobile": [
        _c("Viewport Not Set", "VIEWPORT_MISSING"),
        _o("Content Not Sized Correctly", "needs a rendered mobile layout to measure overflow"),
        _o("Illegible Font Size", "needs computed styles from a rendered page"),
        _g("Contains Unsupported Plugins", "object/embed elements are not extracted"),
        _o("Target Size", "needs rendered hit-box geometry"),
        _g("Mobile Alternate Link", "rel=alternate media annotations are not read"),
    ],
    "Accessibility": [],  # filled below: one decision, 92 entries
    "Analytics": [
        _o("Orphan URLs", "needs Google Analytics data; see the free-sources issue (#97)"),
        _o("Bounce Rate Above 70%", "needs Google Analytics data"),
        _o("No GA Data", "needs Google Analytics data"),
        _o("Non-Indexable with GA Data", "needs Google Analytics data"),
    ],
    "Search Console": [
        _o("Page is Not Mobile Friendly", "needs Search Console; see #97"),
        _o("Orphan URLs", "needs Search Console"),
        _o("URL is on Google, But Has Issues", "needs Search Console"),
        _o("AMP URL is Invalid", "needs Search Console, and AMP is retired"),
        _o("Rich Result is Invalid", "needs Search Console"),
        _o("Indexable URL Not Indexed", "needs Search Console"),
        _o("User-Declared Canonical Not Selected", "needs Search Console"),
        _o("No Search Analytics Data", "needs Search Console"),
        _o("Non-Indexable with Search Analytics Data", "needs Search Console"),
        _o("URL Is Not on Google", "needs Search Console"),
    ],
    "Validation": [
        _g("Missing <head> Tag", "document skeleton validity is not asserted"),
        _g("Multiple <head> Tags", "document skeleton validity is not asserted"),
        _g("Missing <body> Tag", "document skeleton validity is not asserted"),
        _g("Multiple <body> Tags", "document skeleton validity is not asserted"),
        _c("HTML Document Over 2MB", "LARGE_HTML"),
        _p(
            "Resource Over 2MB",
            "a body above the configured ceiling is recorded and not parsed; it is a limit, "
            "not a finding",
        ),
        _g("Invalid HTML Elements In <head>", "element position within the document is not read"),
        _g("<body> Element Preceding <html>", "document skeleton validity is not asserted"),
        _g("<head> Not First In <html> Element", "document skeleton validity is not asserted"),
        _o(
            "High Carbon Rating",
            "a derived score over transfer weight; the weight itself is already reported and "
            "the rating adds a model, not a measurement",
        ),
    ],
    "AMP": [],  # filled below: one decision, 16 entries
}

# Two categories are a single decision rather than 108 separate ones. Listing each row would
# imply each was considered on its own merits; it was not, and pretending otherwise would make
# the map look more thorough than it is.
_ACCESSIBILITY_NOTE = (
    "A full WCAG/axe-core engine. Real, valuable, and a different product: it needs a rendered "
    "DOM, computed styles and a rule set larger than this entire registry. Out of scope until "
    "that is a deliberate decision with its own design, not a checkbox."
)
_AMP_NOTE = (
    "AMP is effectively retired: Google dropped the Top Stories carousel requirement in 2021 "
    "and the format is in maintenance. Building sixteen checks for it now would be work aimed "
    "at the last decade."
)


def _bulk(names: list[str], note: str) -> list[Entry]:
    return [_o(name, note) for name in names]


# The rule names are listed in full rather than counted, so the decision is auditable: a
# reader can see exactly what is being declined.
ACCESSIBILITY_RULES = [
    "Best Practice - Accesskey Attribute Value Must Be Unique",
    "Best Practice - Elements Must Not Have Tabindex Greater Than Zero",
    "Best Practice - ARIA Dialog & Alertdialog Require Accessible Name",
    "Best Practice - ARIA Treeitem Nodes Require Accessible Name",
    "Best Practice - Role=text Should Have No Focusable Descendants",
    "Best Practice - Form Elements Should Have Visible Label",
    "Best Practice - Frames Should Be Tested With axe-core",
    "Best Practice - Scope Attribute Should Be Used Correctly On Tables",
    "WCAG 2.0 A - Scrollable Region Requires Keyboard Access",
    "WCAG 2.0 A - Required ARIA Attributes Must Be Provided",
    "WCAG 2.0 A - ARIA Attribute Must Be Used As Specified For Role",
    "WCAG 2.0 A - ARIA Attributes Require Valid Values",
    "WCAG 2.0 A - ARIA Attributes Require Valid Names",
    "WCAG 2.0 A - ARIA Commands Require Accessible Name",
    "WCAG 2.0 A - ARIA Input Fields Require Accessible Name",
    "WCAG 2.0 A - ARIA Meter Nodes Require Accessible Name",
    "WCAG 2.0 A - ARIA Progressbar Nodes Require Accessible Name",
    "WCAG 2.0 A - ARIA Roles Must Be Contained By Required Parent",
    "WCAG 2.0 A - ARIA Roles Require Valid Values",
    "WCAG 2.0 A - ARIA Toggle Fields Require Accessible Name",
    "WCAG 2.0 A - ARIA Tooltip Nodes Require Accessible Name",
    "WCAG 2.0 A - Certain ARIA Roles Must Contain Specific Children",
    "WCAG 2.0 A - Aria-braille Require Non-braille Equivalent",
    "WCAG 2.0 A - Aria-hidden Elements Contains Focusable Elements",
    "WCAG 2.0 A - Aria-hidden=true Must Not Be Used In <body>",
    "WCAG 2.0 A - Elements Must Only Use Permitted ARIA Attributes",
    "WCAG 2.0 A - Elements Must Use Allowed ARIA Attributes",
    "WCAG 2.0 A - IDs Used In ARIA & Labels Must Be Unique",
    "WCAG 2.0 A - Page Requires Means To Bypass Repeated Blocks",
    "WCAG 2.0 A - Form <input> Elements Require Labels",
    "WCAG 2.0 A - Frames Require Title Attribute",
    "WCAG 2.0 A - Frames Require Unique Title Attribute",
    "WCAG 2.0 A - Frames With Focusable Content Must Not Use tabindex=-1",
    "WCAG 2.0 A - Page Must Contain <title>",
    "WCAG 2.0 A - HTML Element Lang Attribute Value Must Be Valid",
    "WCAG 2.0 A - HTML Element Requires Lang Attribute",
    "WCAG 2.0 A - Image Button Requires Alternate Text",
    "WCAG 2.0 A - Images Require Alternate Text",
    "WCAG 2.0 A - <object> Elements Require Alternate Text",
    "WCAG 2.0 A - Active <area> Elements Require Alternate Text",
    "WCAG 2.0 A - Elements Marked role=img Require Alternate Text",
    "WCAG 2.0 A - SVG Images & Graphics Require Accessible Text",
    "WCAG 2.0 A - <video> Elements Require <track> For Captions",
    "WCAG 2.0 A - <video> or <audio> Elements Must Not Auto-play",
    "WCAG 2.0 A - Buttons Require Discernible Text",
    "WCAG 2.0 A - Input Buttons Require Discernible Text",
    "WCAG 2.0 A - Links Require Discernible Text",
    "WCAG 2.0 A - Links Must Be Distinguishable",
    "WCAG 2.0 A - Select Element Requires Accessible Name",
    "WCAG 2.0 A - Summary Elements Require Discernible Text",
    "WCAG 2.0 A - Deprecated <marquee> Element Must Not Be Used",
    "WCAG 2.0 A - Interactive Controls Must Not Be Nested",
    "WCAG 2.0 A - List Items Must Be Contained In List Elements",
    "WCAG 2.0 A - Lists Must Only Contain <li> Content Elements",
    "WCAG 2.0 A - <dt> & <dd> Elements Must Be Contained by <dl>",
    "WCAG 2.0 A - <dl> Must Only Have Ordered <dt> & <dd> Groups",
    "WCAG 2.0 A - <blink> Elements Deprecated & Must Not Be Used",
    "WCAG 2.0 A - <th> Element Requires Associated Data Cells",
    "WCAG 2.0 A - Table Header Attr Must Refer To Cell In Same Table",
    "WCAG 2.0 AA - Meta Viewport Zoom & Scaling Disabled",
    "WCAG 2.0 AA - Lang Attribute Requires Valid Value",
    "WCAG 2.0 AA - Text Requires Higher Color Contrast to Background",
    "WCAG 2.0 AAA - Text Requires Higher Color Contrast Ratio",
    "WCAG 2.1 AA - Autocomplete Attribute Must Be Used Correctly",
    "WCAG 2.1 AA - Inline Text Spacing Must Be Adjustable",
    "WCAG 2.2 AA - Touch Targets Require Sufficient Size & Spacing",
    "Best Practice - Skip-link Target Should Exist & Be Focusable",
    "Best Practice - All Page Content Must Be Contained By Landmarks",
    "Best Practice - Page Requires One Main Landmark",
    "Best Practice - Page Must Not Have More Than One Banner Landmark",
    "Best Practice - Banner Landmark Must Not Be In Another Landmark",
    "Best Practice - Page Must Not Have Multiple Contentinfo Landmarks",
    "Best Practice - Page Requires At Most One Main Landmark",
    "Best Practice - Complementary Landmarks & Asides Must Be Top Level",
    "Best Practice - Contentinfo Landmark Must Be Top Level Landmark",
    "Best Practice - Main Landmark Must Not Be In Another Landmark",
    "Best Practice - Landmarks Require Unique Role Or Accessible Name",
    "Best Practice - Page Must Contain <h1>",
    "Best Practice - Heading Levels Should Only Increase By One",
    "WCAG 2.0 A - Form Field Must Not Have Multiple Label Elements",
    "WCAG 2.0 A - HTML Lang & XML Lang Value Should Match",
    "Best Practice - Ensure Elements Marked Presentational Are Ignored",
    "Best Practice - ARIA Role Should Be Appropriate For Element",
    "Best Practice - Headings Should Not Be Empty",
    "Best Practice - Meta Viewport Should Allow Zoom & Scale Up to 500%",
    "Best Practice - Alt Text Should Not Be Repeated As Text",
    "Best Practice - Table Headers Require Discernible Text",
    "Best Practice - Table With Identical Summary & Caption Text",
    "WCAG 2.0 A - Deprecated ARIA Roles Must Not Be Used",
    "WCAG 2.0 A - Server-Side Image Maps Must Not Be Used",
    "WCAG 2.0 AAA - Delayed Meta Refresh Must Not Be Used",
    "WCAG 2.0 AAA - Links With Same Accessible Name",
]

AMP_RULES = [
    "Non-200 Response",
    "Missing Non-AMP Return Link",
    "Missing Canonical to Non-AMP",
    "Non-Indexable Canonical",
    "Missing <html amp> Tag",
    "Missing/Invalid Doctype HTML Tag",
    "Missing Head Tag",
    "Missing Body Tag",
    "Missing Canonical",
    "Missing/Invalid Meta Charset Tag",
    "Missing/Invalid Meta Viewport Tag",
    "Missing/Invalid AMP Script",
    "Missing/Invalid AMP Boilerplate",
    "Contains Disallowed HTML",
    "Other Validation Errors",
    "Indexable",
]

CATEGORIES["Accessibility"] = _bulk(ACCESSIBILITY_RULES, _ACCESSIBILITY_NOTE)
CATEGORIES["AMP"] = _bulk(AMP_RULES, _AMP_NOTE)


def entries() -> list[tuple[str, Entry]]:
    """Every catalogued issue, as (category, entry)."""
    return [(category, entry) for category, items in CATEGORIES.items() for entry in items]


def coverage_counts() -> dict[str, int]:
    counts: dict[str, int] = dict.fromkeys(STATUSES, 0)
    for _category, entry in entries():
        counts[entry.status] += 1
    return counts
