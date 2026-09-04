"""Structured on-page SEO parser.

Fetches a URL with browser-compatible request headers (httpx follows redirects and
transparently decodes gzip/deflate/br), then extracts the on-page SEO
signals a specialist cares about: title, meta description, canonical,
robots, Open Graph / Twitter tags, the H1..H6 heading outline, JSON-LD
blocks, links (with rel / nofollow / external flags), and the collapsed
visible body text with a word count. Word count is scoped to a configurable
content area (see ``content_area.py``) so navigation and footer boilerplate
does not inflate it; link discovery always covers the whole document.

BeautifulSoup (``features="lxml"``) provides robust HTML parsing. Relative URLs
(links, canonical) are resolved against the
*final* URL after redirects. Any fetch/parse failure is reported as a
plain ``{"url", "ok": False, "error"}`` dict rather than raising.

Public API:
    parse_url(url, options=None) -> dict
"""

from __future__ import annotations

import re
from collections.abc import Callable
from html import unescape
from typing import Any, cast
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from seohead.models import LinkInfo, ParsedPage, ParseResult
from seohead.recon.net import http_client
from seohead.tools.content_area import extract_area_text, resolve_content_area

# Browser-like User-Agent: without it, bot protection (Cloudflare et al.)
# tends to serve a challenge/block page instead of the real document.
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Accept-Encoding is intentionally omitted here: httpx sets it itself and
# transparently decompresses gzip/deflate/br. The rest mirror a real
# navigation request (identity/no headers = an obvious bot signature).
DEFAULT_HEADERS = {
    "User-Agent": DEFAULT_UA,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

# Which extractions run by default. Each may be switched off via options.
_OPTION_KEYS = ("meta", "canonical", "og", "headings", "jsonld", "links", "text", "url_sources")

# URL-bearing attributes beyond a[href]: media, forms, citations, ping,
# meta-refresh, and itemtype. This covers carriers that a crawler or auditor
# would miss by inspecting only anchor elements.
_URL_SOURCE_ATTRS = {
    "img": ("src", "srcset"),
    "source": ("src", "srcset"),
    "script": ("src",),
    "link": ("href",),
    "iframe": ("src",),
    "embed": ("src",),
    "video": ("src", "poster"),
    "audio": ("src",),
    "track": ("src",),
    "input": ("src", "formaction"),
    "button": ("formaction",),
    "form": ("action",),
    "a": ("ping",),
    "blockquote": ("cite",),
    "q": ("cite",),
    "del": ("cite",),
    "ins": ("cite",),
    "object": ("data",),
}

DEFAULT_TIMEOUT = 15.0
_MAX_REDIRECTS = 8

# ── PURE HELPERS ──────────────────────────────────────────────────────────────


def collapse_whitespace(text: str | None) -> str:
    """Collapse all runs of whitespace to single spaces and trim.

    Mirrors ``stripTags``'s ``\\s+ -> ' '`` + ``trim`` step. Also decodes
    HTML entities so callers get human-readable text.
    """
    if not text:
        return ""
    return " ".join(unescape(str(text)).split())


def is_external(href_abs: str, base_url: str) -> bool:
    """True when ``href_abs`` points to a different host than ``base_url``.

    Hostname comparison is case-insensitive. A URL that cannot be parsed,
    or one lacking a host (e.g. a bare fragment resolved oddly), is treated
    as internal — matching the TS ``abs.startsWith(base)`` intent that a
    same-origin URL is internal.
    """
    try:
        target = urlparse(href_abs).hostname or ""
        base = urlparse(base_url).hostname or ""
    except ValueError:
        return False
    if not target:
        return False
    return target.lower() != base.lower()


def _resolve_options(options: dict[str, Any] | None) -> dict[str, bool]:
    """Normalize the options dict: every flag defaults to True except url_sources."""
    options = options or {}
    return {key: bool(options.get(key, key != "url_sources")) for key in _OPTION_KEYS}


def _meta_content(soup: BeautifulSoup, *, name: str) -> str | None:
    """Return the ``content`` of ``<meta name=...>`` (case-insensitive)."""
    tag = soup.find("meta", attrs={"name": _ci(name)})
    # "content" is not one of BeautifulSoup's multi-valued attributes, so this
    # is always a plain string at runtime; the stub types it broadly because
    # .get() is generic across every attribute.
    content = cast("str | None", tag.get("content")) if tag else None
    if content is not None:
        return collapse_whitespace(content)
    return None


# <title> also exists in the SVG and MathML vocabularies, where it is an
# accessible name for a graphic, not the title of the document. An inline icon
# therefore places a <title> before the real one — often before any <title> at
# all — and BeautifulSoup's ``soup.title`` returns the first in document order.
_FOREIGN_CONTENT = ("svg", "math")


def document_title(soup: BeautifulSoup) -> str | None:
    """Return the HTML document title, ignoring SVG/MathML ``<title>``."""
    for tag in soup.find_all("title"):
        if any(parent.name in _FOREIGN_CONTENT for parent in tag.parents):
            continue
        return collapse_whitespace(tag.get_text()) or None
    return None


# A robots directive is addressed to a named crawler; ``robots`` addresses all
# of them. Google reads the union of the generic tag and the ones naming it, so
# a page can be noindex without the word appearing in <meta name="robots">.
ROBOTS_META_NAMES = (
    "robots",
    "googlebot",
    "googlebot-news",
    "bingbot",
    "msnbot",
    "yandex",
    "slurp",
)

# Directives that carry a value after a colon, so the colon is not a
# user-agent prefix.
_VALUED_DIRECTIVES = (
    "max-snippet",
    "max-image-preview",
    "max-video-preview",
    "unavailable_after",
)


def robots_meta_values(soup: BeautifulSoup) -> list[str]:
    """Return the ``content`` of every robots-directive meta, in document order."""
    out: list[str] = []
    for tag in soup.find_all("meta"):
        name = tag.get("name")
        if not isinstance(name, str) or name.lower() not in ROBOTS_META_NAMES:
            continue
        content = tag.get("content")
        if isinstance(content, str) and content.strip():
            out.append(collapse_whitespace(content))
    return out


def robots_directives(*values: str | None) -> set[str]:
    """Split robots directive strings into lowercase tokens.

    Handles the two forms that defeat a substring search: ``none``, which is
    shorthand for ``noindex, nofollow``, and the ``<user-agent>: <directive>``
    prefix that an ``X-Robots-Tag`` header may carry.
    """
    tokens: set[str] = set()
    for value in values:
        for raw in str(value or "").replace(";", ",").split(","):
            token = raw.strip().lower()
            if ":" in token and not token.startswith(_VALUED_DIRECTIVES):
                token = token.split(":", 1)[1].strip()
            if not token:
                continue
            tokens.add(token)
            if token == "none":
                tokens.update(("noindex", "nofollow"))
    return tokens


def _ci(value: str) -> Callable[[Any], bool]:
    """A case-insensitive attribute matcher for BeautifulSoup ``find``."""
    target = value.lower()
    return lambda v: isinstance(v, str) and v.lower() == target


def _extract_headings(soup: BeautifulSoup) -> dict[str, list[str]]:
    """Return ``{"h1": [...], ..., "h6": [...]}`` for headings that have text."""
    headings: dict[str, list[str]] = {}
    for level in range(1, 7):
        found: list[str] = []
        for tag in soup.find_all(f"h{level}"):
            text = collapse_whitespace(tag.get_text(" "))
            if text:
                found.append(text)
        if found:
            headings[f"h{level}"] = found
    return headings


# How much of a broken block to quote back, so the reader can find it in the
# page without the report carrying the whole thing.
_JSONLD_EXCERPT_CHARS = 200


def _extract_jsonld(soup: BeautifulSoup) -> tuple[list[Any], list[dict[str, Any]]]:
    """Parse every ``<script type="application/ld+json">`` block.

    Returns the blocks that parsed and a record of those that did not. Dropping
    the failures silently makes a page whose markup is broken indistinguishable
    from a page with no markup — the opposite conclusion, and the more common
    one: a single stray comment voids an entire @graph.
    """
    import json

    out: list[Any] = []
    invalid: list[dict[str, Any]] = []
    for index, tag in enumerate(
        soup.find_all("script", attrs={"type": _ci("application/ld+json")}), 1
    ):
        raw = tag.string or tag.get_text()
        text = (raw or "").strip()
        if not text:
            invalid.append({"index": index, "error": "block is empty", "excerpt": ""})
            continue
        try:
            out.append(json.loads(text))
        except (ValueError, TypeError) as exc:
            invalid.append(
                {
                    "index": index,
                    "error": str(exc),
                    "excerpt": text[:_JSONLD_EXCERPT_CHARS],
                }
            )
    return out, invalid


_BASE_HREF_RE = re.compile(r"<base\b[^>]*?\bhref\s*=\s*[\"']([^\"']*)[\"']", re.IGNORECASE)


def document_base_url(document: BeautifulSoup | str, final_url: str) -> str:
    """Return the document base URL for resolving relative links.

    Per the HTML standard relative URLs resolve against the ``href`` of the
    **first** ``<base>`` element that carries one — itself resolved against the
    document URL — and against the document URL when there is no such element.

    Ignoring this reports links that do not exist: on a page whose base is
    ``https://example.com/`` a relative ``catalog/`` resolves to
    ``https://example.com/catalog/``, not to a path under the current
    directory. Sites that ship a ``<base>`` tag (MODX and older CMS themes do)
    otherwise produce a flood of phantom broken links that a browser and a
    search engine crawler both fetch with a 200.

    ``document`` accepts parsed markup or raw HTML; the raw form exists for
    callers that deliberately avoid the cost of building a tree.
    """
    href = ""
    if isinstance(document, str):
        match = _BASE_HREF_RE.search(document)
        if match:
            href = match.group(1).strip()
    else:
        for tag in document.find_all("base"):
            # "href" is single-valued, so this is always a plain string.
            candidate = (cast("str | None", tag.get("href")) or "").strip()
            if candidate:
                href = candidate
                break
    if not href:
        return final_url
    try:
        return urljoin(final_url, href)
    except ValueError:
        return final_url


def _extract_links(soup: BeautifulSoup, base_url: str, final_url: str) -> list[LinkInfo]:
    """Collect ``<a href>`` links resolved against ``base_url``.

    ``base_url`` resolves the hrefs; ``final_url`` decides what counts as
    external, because "external" means a host other than the page's own —
    a ``<base>`` pointing elsewhere must not reclassify the whole page.

    Skips empty hrefs and ``javascript:`` / ``mailto:`` / ``tel:`` /
    pure-fragment (``#...``) links. Each entry carries the resolved absolute
    href, anchor text, rel tokens, a ``nofollow`` flag, and an ``external``
    flag.
    """
    links: list[LinkInfo] = []
    for tag in soup.find_all("a"):
        # "href" is single-valued, so this is always a plain string.
        href_raw = (cast("str | None", tag.get("href")) or "").strip()
        if not href_raw:
            continue
        lowered = href_raw.lower()
        if (
            href_raw.startswith("#")
            or lowered.startswith("javascript:")
            or lowered.startswith("mailto:")
            or lowered.startswith("tel:")
        ):
            continue
        try:
            abs_href = urljoin(base_url, href_raw)
        except ValueError:
            continue
        rel_attr: str | list[str] = tag.get("rel") or []
        # BeautifulSoup returns rel as a list; normalize to lowercase tokens.
        rel_tokens = rel_attr.split() if isinstance(rel_attr, str) else list(rel_attr)
        rel_tokens = [t.lower() for t in rel_tokens]
        links.append(
            {
                "href": abs_href,
                "text": collapse_whitespace(tag.get_text(" ")),
                "rel": " ".join(rel_tokens),
                "nofollow": "nofollow" in rel_tokens,
                "external": is_external(abs_href, final_url),
            }
        )
    return links


def _extract_text(soup: BeautifulSoup) -> str:
    """Collapsed visible body text (script/style removed)."""
    body = soup.body or soup
    # Work on a copy so we don't mutate the shared tree used by other steps.
    from copy import copy

    body = copy(body)
    for tag in body.find_all(["script", "style", "noscript", "template"]):
        tag.decompose()
    return collapse_whitespace(body.get_text(" "))


# srcset entries use ``URL descriptor``; retain the URL before the first space.
_SRCSET_SPLIT = re.compile(r"\s*,\s*(?=(?:[^']*$))")


def _split_srcset(value: str) -> list[str]:
    """Extract one URL per srcset entry, discarding density/width descriptors."""
    urls: list[str] = []
    for entry in _SRCSET_SPLIT.split(value):
        entry = entry.strip()
        if not entry:
            continue
        urls.append(entry.split(None, 1)[0])
    return urls


# CSS ``url(...)`` references, in inline style attributes and <style> blocks.
# A page whose banners and product photos are CSS backgrounds is invisible to
# every image check if only <img> is inspected — and a background image has no
# alt attribute at all, which is itself sometimes the finding.
_CSS_URL_RE = re.compile(r"""url\(\s*(['"]?)([^'")]+)\1\s*\)""", re.IGNORECASE)


def extract_css_urls(css_text: str | None) -> list[str]:
    """URLs referenced from CSS text, in source order, duplicates kept.

    Deliberately not limited to ``background-image``: ``border-image``,
    ``list-style-image``, ``mask-image`` and ``content`` all fetch resources the
    same way, and a checker that only knew one property would under-report.
    """
    return [match.group(2).strip() for match in _CSS_URL_RE.finditer(css_text or "")]


def extract_url_sources(soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
    """Extract URL carriers beyond ``a[href]``.

    Covers media, forms, citations, ping, meta-refresh, and itemtype. Each URL
    records the tag and attribute where it was found. Relative references are
    resolved against ``base_url``.
    """
    out: list[dict[str, str]] = []
    seen: set[str] = set()

    def push(raw_url: str, tag_name: str, attr: str) -> None:
        raw_url = (raw_url or "").strip()
        if not raw_url:
            return
        # Skip embedded data, active schemes, contact links, and bare fragments.
        low = raw_url.lower()
        if raw_url.startswith("#") or low.startswith(("data:", "javascript:", "mailto:", "tel:")):
            return
        try:
            absolute = urljoin(base_url, raw_url)
        except ValueError:
            return
        if absolute not in seen:
            seen.add(absolute)
            out.append({"url": absolute, "tag": tag_name, "attr": attr})

    for tag_name, attrs in _URL_SOURCE_ATTRS.items():
        for tag in soup.find_all(tag_name):
            for attr in attrs:
                value = tag.get(attr)
                if not value:
                    continue
                if attr == "srcset":  # one attribute may contain multiple URLs
                    for sub in _split_srcset(value if isinstance(value, str) else " ".join(value)):
                        push(sub, tag_name, attr)
                elif attr == "ping":  # space-separated URL list per the HTML spec
                    for sub in (value if isinstance(value, str) else " ".join(value)).split():
                        push(sub, tag_name, attr)
                else:
                    push(value if isinstance(value, str) else value[0], tag_name, attr)

    # CSS url(...) in inline style attributes and in <style> blocks. External
    # stylesheets are not fetched here: this function parses one document and
    # performs no I/O, so a linked .css is reported as a resource by the <link>
    # rule above and its contents are a crawler concern, not a parser one.
    for tag in soup.find_all(style=True):
        style_value = tag.get("style")
        if isinstance(style_value, list):
            style_value = " ".join(style_value)
        for url in extract_css_urls(style_value):
            push(url, tag.name, "style")
    for style_tag in soup.find_all("style"):
        for url in extract_css_urls(style_tag.get_text()):
            push(url, "style", "css")

    # meta http-equiv=refresh content="0;url=..."
    for meta in soup.find_all("meta"):
        equiv = meta.get("http-equiv") or ""
        if isinstance(equiv, list):
            equiv = " ".join(equiv)
        if equiv.lower().strip() == "refresh":
            # "content" is single-valued, so this is always a plain string.
            content = cast("str | None", meta.get("content")) or ""
            match = re.search(r"url\s*=\s*['\"]?([^\s'\"]+)", content, re.IGNORECASE)
            if match:
                push(match.group(1), "meta", "refresh")

    # itemtype is a microdata vocabulary URL rather than a resource URL, but it
    # is still a useful carrier for an auditor to inspect.
    for tag in soup.select("[itemtype]"):
        value = tag.get("itemtype")
        if isinstance(value, list):
            for v in value:
                push(v, tag.name, "itemtype")
        elif isinstance(value, str):
            push(value, tag.name, "itemtype")

    return out


# extract_url_sources() also carries non-image carriers (script src, form
# action, cite, itemtype, ...). "img"/"source" are always an image; any other
# tag only qualifies via its "style" or "css" attr, i.e. a CSS url() -- which
# is how a background-image (no <img>, no alt attribute) is reported at all.
_IMAGE_URL_SOURCE_ATTRS = ("style", "css")


def image_url_sources(url_sources: list[dict[str, str]]) -> list[dict[str, str]]:
    """Filter ``extract_url_sources()`` output down to entries that are images."""
    return [
        s
        for s in url_sources
        if s["tag"] in ("img", "source") or s["attr"] in _IMAGE_URL_SOURCE_ATTRS
    ]


def parse_html(html: str, final_url: str, options: dict[str, Any] | None = None) -> ParsedPage:
    """Extract SEO data from an HTML string (pure — no network).

    Honors each option flag; skips the corresponding extraction when False.
    ``final_url`` is used to resolve relative links and the canonical URL.
    """
    opts = _resolve_options(options)
    soup = BeautifulSoup(html, features="lxml")
    # Everything that turns markup into absolute URLs resolves against the
    # document base, not the page URL: see document_base_url.
    base_url = document_base_url(soup, final_url)

    result: dict[str, Any] = {}

    if opts["meta"]:
        result["title"] = document_title(soup)
        result["meta_description"] = _meta_content(soup, name="description")
        result["robots"] = _meta_content(soup, name="robots")
        # Separate from "robots": that key keeps its literal meaning, this one
        # carries every crawler-addressed tag, which is what indexability needs.
        result["robots_meta"] = robots_meta_values(soup)
    else:
        result["title"] = None
        result["meta_description"] = None
        result["robots"] = None
        result["robots_meta"] = []

    if opts["canonical"]:
        canonical_tag = soup.find("link", attrs={"rel": _rel_has("canonical")})
        # "href" is single-valued, so this is always a plain string.
        href = cast("str | None", canonical_tag.get("href")) if canonical_tag else None
        result["canonical"] = urljoin(base_url, href.strip()) if href else None
    else:
        result["canonical"] = None

    if opts["og"]:
        og: dict[str, str] = {}
        twitter: dict[str, str] = {}
        for tag in soup.find_all("meta"):
            # "content" is single-valued, so this is always a plain string.
            content = cast("str | None", tag.get("content"))
            if content is None:
                continue
            prop = tag.get("property")
            if isinstance(prop, str) and prop.lower().startswith("og:"):
                og[prop.strip()] = collapse_whitespace(content)
                continue
            name = tag.get("name")
            if isinstance(name, str) and name.lower().startswith("twitter:"):
                twitter[name.strip()] = collapse_whitespace(content)
        result["og"] = og
        result["twitter"] = twitter
    else:
        result["og"] = {}
        result["twitter"] = {}

    result["headings"] = _extract_headings(soup) if opts["headings"] else {}
    # jsonld stays what it has always been — the blocks that parsed — and the
    # ones that did not are reported beside it rather than dropped.
    if opts["jsonld"]:
        result["jsonld"], result["jsonld_invalid"] = _extract_jsonld(soup)
    else:
        result["jsonld"], result["jsonld_invalid"] = [], []
    result["links"] = _extract_links(soup, base_url, final_url) if opts["links"] else []
    # url_sources covers carriers beyond a[href] (srcset, ping, formaction,
    # cite, meta-refresh, itemtype). It is off by default to preserve the links contract.
    if opts["url_sources"]:
        result["url_sources"] = extract_url_sources(soup, base_url)

    if opts["text"]:
        text = _extract_text(soup)
        result["text"] = text
        # Word count is scoped to the content area (nav/footer excluded by
        # default) so a mega-menu can't make a thin page look substantial;
        # "text" above stays whole-body on purpose. page_facts.py's schema
        # evidence (sameAs social links, breadcrumbs, price/rating regexes)
        # depends on facts that legitimately live in header/footer widgets the
        # content area excludes, so scoping "text" would silently cost that
        # evidence. citability_check(url=...) does not read this field either
        # way: it scores markdown_extract's content-area Markdown instead,
        # because "text" is a single collapsed line with no paragraph or
        # heading breaks for the scorer to find. Link discovery never sees the
        # resolved root, so restricting text never restricts the crawl.
        content_config = options.get("content_area") if isinstance(options, dict) else None
        content_root, strategy = resolve_content_area(soup, content_config)
        content_text = extract_area_text(content_root)
        result["content_text"] = content_text
        result["content_area_strategy"] = strategy
        result["word_count"] = len(content_text.split())
    else:
        result["text"] = ""
        result["content_text"] = ""
        result["content_area_strategy"] = None
        result["word_count"] = 0

    # Built imperatively above (one assignment per option branch) rather than as
    # one literal, so a plain dict is the natural builder; cast once at the
    # boundary instead of restructuring the loop above around a TypedDict literal.
    return cast(ParsedPage, result)


def _rel_has(token: str) -> Callable[[Any], bool]:
    """Match a ``rel`` attribute (list or string) that contains ``token``."""
    target = token.lower()

    def _matcher(value: Any) -> bool:
        if value is None:
            return False
        tokens = value.split() if isinstance(value, str) else list(value)
        return any(isinstance(t, str) and t.lower() == target for t in tokens)

    return _matcher


# ── FETCH + PARSE ─────────────────────────────────────────────────────────────


def fetch_html(url: str, timeout: float | None = None) -> dict[str, Any]:
    """Fetch ``url`` and return its raw response, unparsed.

    ``ok`` reports whether the *request* succeeded, not the HTTP status: a
    404 or 500 still returns ``ok: True`` with the body it sent, exactly
    like ``parse_url`` has always tolerated (a soft-404 page's own markup is
    evidence, not noise). Only a transport failure (DNS, TLS, timeout, ...)
    sets ``ok: False`` with an ``error``. Callers that need something other
    than ``parse_html``'s extraction (Markdown rendering, boilerplate
    hashing, a content-area-only citability score) fetch through this
    function rather than duplicating the request logic.

    Returns ``{"ok", "url", "final_url", "status_code", "html"}`` on a
    completed request, or ``{"ok": False, "url", "error"}`` on a transport
    failure.
    """
    try:
        resolved_timeout = float(timeout or DEFAULT_TIMEOUT)
    except (TypeError, ValueError):
        resolved_timeout = DEFAULT_TIMEOUT
    try:
        client, _http2_capable = http_client(
            resolved_timeout,
            headers=DEFAULT_HEADERS,
            follow_redirects=True,
            max_redirects=_MAX_REDIRECTS,
        )
        with client:
            response = client.get(url)
        return {
            "ok": True,
            "url": url,
            "final_url": str(response.url),
            "status_code": response.status_code,
            "html": response.text,
        }
    except Exception as exc:
        return {"ok": False, "url": url, "error": str(exc)}


def parse_url(url: str, options: dict[str, Any] | None = None) -> ParseResult:
    """Fetch ``url`` and return its extracted SEO data.

    ``options`` accepts the boolean flags ``meta``, ``canonical``, ``og``,
    ``headings``, ``jsonld``, ``links`` and ``text`` (all default True). A
    ``timeout`` (seconds) may also be provided, and a ``content_area`` dict
    configures the region ``word_count`` is scoped to — see
    ``content_area.resolve_content_area`` for its keys.

    On success returns a dict with keys: ``url``, ``final_url``,
    ``status_code``, ``ok``, ``title``, ``meta_description``, ``canonical``,
    ``robots``, ``og``, ``twitter``, ``headings``, ``jsonld``, ``links``,
    ``text``, ``content_text``, ``content_area_strategy`` and ``word_count``.

    On any fetch or parse error returns ``{"url", "ok": False, "error"}``
    rather than raising.
    """
    opts = options or {}
    fetched = fetch_html(url, timeout=opts.get("timeout"))
    if not fetched["ok"]:
        return fetched
    data = parse_html(fetched["html"], fetched["final_url"], options)
    return {
        "url": url,
        "final_url": fetched["final_url"],
        "status_code": fetched["status_code"],
        "ok": 200 <= fetched["status_code"] < 300,
        **data,
    }


# ── SMOKE TEST (no network) ───────────────────────────────────────────────────

if __name__ == "__main__":
    sample = """
    <html lang="en">
      <head>
        <title>Example &amp; Co</title>
        <meta name="description" content="A short   description.">
        <meta name="robots" content="index, follow">
        <link rel="canonical" href="/canonical-page">
        <meta property="og:title" content="OG Title">
        <meta name="twitter:card" content="summary">
        <script type="application/ld+json">{"@type": "Article", "name": "X"}</script>
      </head>
      <body>
        <h1>Main Heading</h1>
        <h2>Sub</h2>
        <a href="/internal">Internal</a>
        <a href="https://other.example.org/x" rel="nofollow noopener">External</a>
        <a href="mailto:a@b.com">Mail</a>
        <p>Hello   world  from the body.</p>
        <script>ignore()</script>
      </body>
    </html>
    """
    parsed = parse_html(sample, "https://example.com/page")

    assert parsed["title"] == "Example & Co", parsed["title"]
    assert parsed["meta_description"] == "A short description."
    assert parsed["robots"] == "index, follow"
    assert parsed["canonical"] == "https://example.com/canonical-page", parsed["canonical"]
    assert parsed["og"] == {"og:title": "OG Title"}, parsed["og"]
    assert parsed["twitter"] == {"twitter:card": "summary"}, parsed["twitter"]
    assert parsed["headings"] == {"h1": ["Main Heading"], "h2": ["Sub"]}, parsed["headings"]
    assert parsed["jsonld"] == [{"@type": "Article", "name": "X"}], parsed["jsonld"]

    hrefs = {link["href"]: link for link in parsed["links"]}
    assert "https://example.com/internal" in hrefs
    assert "https://other.example.org/x" in hrefs
    assert not hrefs["https://example.com/internal"]["external"]
    assert hrefs["https://other.example.org/x"]["external"]
    assert hrefs["https://other.example.org/x"]["nofollow"]
    assert all("mailto" not in h for h in hrefs)  # mailto skipped

    assert "Hello world from the body." in parsed["text"]
    assert "ignore" not in parsed["text"]  # script stripped
    assert parsed["word_count"] > 0

    # Option flags disable their extraction.
    off = parse_html(sample, "https://example.com/page", {"headings": False, "links": False})
    assert off["headings"] == {}
    assert off["links"] == []
    assert off["title"] == "Example & Co"  # meta still on

    # is_external edge cases.
    assert is_external("https://a.com/x", "https://b.com/y")
    assert not is_external("https://a.com/x", "https://a.com/y")
    assert not is_external("https://A.com/x", "https://a.com/y")  # case-insensitive

    print("OK: parser smoke test passed")
