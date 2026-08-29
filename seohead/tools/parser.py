"""Structured on-page SEO parser.

Fetches a URL with browser-compatible request headers (httpx follows redirects and
transparently decodes gzip/deflate/br), then extracts the on-page SEO
signals a specialist cares about: title, meta description, canonical,
robots, Open Graph / Twitter tags, the H1..H6 heading outline, JSON-LD
blocks, links (with rel / nofollow / external flags), and the collapsed
visible body text with a word count.

BeautifulSoup (``features="lxml"``) provides robust HTML parsing. Relative URLs
(links, canonical) are resolved against the
*final* URL after redirects. Any fetch/parse failure is reported as a
plain ``{"url", "ok": False, "error"}`` dict rather than raising.

Public API:
    parse_url(url, options=None) -> dict
"""

from __future__ import annotations

import re
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from seohead.recon.net import http_client

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


def _resolve_options(options: dict | None) -> dict[str, bool]:
    """Normalize the options dict: every flag defaults to True except url_sources."""
    options = options or {}
    return {key: bool(options.get(key, key != "url_sources")) for key in _OPTION_KEYS}


def _meta_content(soup: BeautifulSoup, *, name: str) -> str | None:
    """Return the ``content`` of ``<meta name=...>`` (case-insensitive)."""
    tag = soup.find("meta", attrs={"name": _ci(name)})
    if tag and tag.get("content") is not None:
        return collapse_whitespace(tag.get("content"))
    return None


def _ci(value: str):
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


def _extract_jsonld(soup: BeautifulSoup) -> list[Any]:
    """Parse every ``<script type="application/ld+json">`` block.

    Blocks that fail to parse as JSON are skipped (the TS version swallows
    the error and moves on).
    """
    import json

    out: list[Any] = []
    for tag in soup.find_all("script", attrs={"type": _ci("application/ld+json")}):
        raw = tag.string or tag.get_text()
        if not raw:
            continue
        try:
            out.append(json.loads(raw.strip()))
        except (ValueError, TypeError):
            continue
    return out


def _extract_links(soup: BeautifulSoup, final_url: str) -> list[dict[str, Any]]:
    """Collect ``<a href>`` links resolved against ``final_url``.

    Skips empty hrefs and ``javascript:`` / ``mailto:`` / ``tel:`` /
    pure-fragment (``#...``) links. Each entry carries the resolved absolute
    href, anchor text, rel tokens, a ``nofollow`` flag, and an ``external``
    flag.
    """
    links: list[dict[str, Any]] = []
    for tag in soup.find_all("a"):
        href_raw = (tag.get("href") or "").strip()
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
            abs_href = urljoin(final_url, href_raw)
        except ValueError:
            continue
        rel_attr = tag.get("rel") or []
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

    # meta http-equiv=refresh content="0;url=..."
    for meta in soup.find_all("meta"):
        equiv = meta.get("http-equiv") or ""
        if isinstance(equiv, list):
            equiv = " ".join(equiv)
        if equiv.lower().strip() == "refresh":
            content = meta.get("content") or ""
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


def parse_html(html: str, final_url: str, options: dict | None = None) -> dict[str, Any]:
    """Extract SEO data from an HTML string (pure — no network).

    Honors each option flag; skips the corresponding extraction when False.
    ``final_url`` is used to resolve relative links and the canonical URL.
    """
    opts = _resolve_options(options)
    soup = BeautifulSoup(html, features="lxml")

    result: dict[str, Any] = {}

    if opts["meta"]:
        title_tag = soup.title
        result["title"] = (collapse_whitespace(title_tag.get_text()) if title_tag else None) or None
        result["meta_description"] = _meta_content(soup, name="description")
        result["robots"] = _meta_content(soup, name="robots")
    else:
        result["title"] = None
        result["meta_description"] = None
        result["robots"] = None

    if opts["canonical"]:
        canonical_tag = soup.find("link", attrs={"rel": _rel_has("canonical")})
        href = canonical_tag.get("href") if canonical_tag else None
        result["canonical"] = urljoin(final_url, href.strip()) if href else None
    else:
        result["canonical"] = None

    if opts["og"]:
        og: dict[str, str] = {}
        twitter: dict[str, str] = {}
        for tag in soup.find_all("meta"):
            content = tag.get("content")
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
    result["jsonld"] = _extract_jsonld(soup) if opts["jsonld"] else []
    result["links"] = _extract_links(soup, final_url) if opts["links"] else []
    # url_sources covers carriers beyond a[href] (srcset, ping, formaction,
    # cite, meta-refresh, itemtype). It is off by default to preserve the links contract.
    if opts["url_sources"]:
        result["url_sources"] = extract_url_sources(soup, final_url)

    if opts["text"]:
        text = _extract_text(soup)
        result["text"] = text
        result["word_count"] = len(text.split())
    else:
        result["text"] = ""
        result["word_count"] = 0

    return result


def _rel_has(token: str):
    """Match a ``rel`` attribute (list or string) that contains ``token``."""
    target = token.lower()

    def _matcher(value) -> bool:
        if value is None:
            return False
        tokens = value.split() if isinstance(value, str) else list(value)
        return any(isinstance(t, str) and t.lower() == target for t in tokens)

    return _matcher


# ── FETCH + PARSE ─────────────────────────────────────────────────────────────


def parse_url(url: str, options: dict | None = None) -> dict[str, Any]:
    """Fetch ``url`` and return its extracted SEO data.

    ``options`` accepts the boolean flags ``meta``, ``canonical``, ``og``,
    ``headings``, ``jsonld``, ``links`` and ``text`` (all default True). A
    ``timeout`` (seconds) may also be provided.

    On success returns a dict with keys: ``url``, ``final_url``,
    ``status_code``, ``ok``, ``title``, ``meta_description``, ``canonical``,
    ``robots``, ``og``, ``twitter``, ``headings``, ``jsonld``, ``links``,
    ``text`` and ``word_count``.

    On any fetch or parse error returns ``{"url", "ok": False, "error"}``
    rather than raising.
    """
    opts = options or {}
    try:
        timeout = float(opts.get("timeout") or DEFAULT_TIMEOUT)
    except (TypeError, ValueError):
        timeout = DEFAULT_TIMEOUT

    try:
        client, _http2_capable = http_client(
            timeout,
            headers=DEFAULT_HEADERS,
            follow_redirects=True,
            max_redirects=_MAX_REDIRECTS,
        )
        with client:
            response = client.get(url)
        final_url = str(response.url)
        data = parse_html(response.text, final_url, options)
        return {
            "url": url,
            "final_url": final_url,
            "status_code": response.status_code,
            "ok": response.is_success,
            **data,
        }
    except Exception as exc:
        return {"url": url, "ok": False, "error": str(exc)}


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
