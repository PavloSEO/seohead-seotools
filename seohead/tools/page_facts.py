"""Extract observable page facts from HTML as the basis for a Schema.org graph.

``schema.check_schema`` validates what a site has already declared in JSON-LD.
Building or extending a graph requires a second source of truth: facts visibly
present on the page, including the title, Open Graph metadata, canonical URL,
publication date, price, rating, ``sameAs`` links, and breadcrumbs. Comparing these
facts with JSON-LD reveals disagreements between what a page presents and what its
structured data claims, which isolated block validation cannot detect.

General SEO facts come from the pure ``parser.parse_html`` function, which already
extracts title, Open Graph and Twitter metadata, canonical, headings, JSON-LD,
links, and text. This module adds only Schema-specific evidence and never performs
network access; it operates on supplied HTML.

Every heuristic is labeled. A microdata price is a directly observed fact, while
a currency-like regex match in visible text is returned with ``heuristic=True``.
This preserves the rule that unavailable or uncertain evidence must not be
reported as measured truth.
"""

from __future__ import annotations

import contextlib
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from seohead.tools.parser import collapse_whitespace, document_base_url, parse_html

# Hosts suitable for an organization's ``sameAs`` references.
_SOCIAL_HOSTS = (
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "linkedin.com",
    "youtube.com",
    "youtu.be",
    "vk.com",
    "t.me",
    "telegram.me",
    "tiktok.com",
    "github.com",
    "pinterest.com",
    "threads.net",
)

_PRICE_RE = re.compile(
    r"(?:USD|EUR|GBP|RUB|BYN|₽|\$|€|£)\s?\d+(?:[.,]\d{1,2})?|"
    r"\d+(?:[.,]\d{1,2})?\s?(?:руб|р\.|у\.е\.|USD|EUR)",  # noqa: RUF001 - localized prices
    re.IGNORECASE,
)
_RATING_RE = re.compile(r"(\d(?:[.,]\d{1,2})?)\s*(?:/|из|из\s*)\s*5", re.IGNORECASE)


def _meta_prop(soup: BeautifulSoup, prop: str) -> str | None:
    """Read either ``<meta property=...>`` or ``<meta name=...>``."""
    for selector in ("property", "name"):
        tag = soup.find("meta", attrs={selector: prop})
        if tag and tag.get("content"):
            return collapse_whitespace(tag.get("content"))
    return None


def _article_time(soup: BeautifulSoup, prop: str = "article:published_time") -> str | None:
    val = _meta_prop(soup, prop)
    if val:
        return val
    # ``<time datetime=...>`` is a fallback source for article dates.
    tag = soup.find("time")
    if tag and tag.get("datetime"):
        return collapse_whitespace(tag.get("datetime"))
    return None


def _rel_author(soup: BeautifulSoup) -> str | None:
    """Read author identity from ``<link rel=author>`` or ``<a rel=author>``."""
    tag = soup.find(attrs={"rel": re.compile(r"\bauthor\b", re.IGNORECASE)})
    if tag and tag.get("href"):
        return collapse_whitespace(tag.get("href"))
    return None


def _breadcrumbs(soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
    """Extract breadcrumbs from JSON-LD first, then visible navigation.

    JSON-LD is read here only as a fact source; ``schema.check_schema`` remains
    responsible for validating its structure and vocabulary.
    """
    out: list[dict[str, str]] = []
    # Prefer a JSON-LD BreadcrumbList when available.
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (tag.string or tag.get_text() or "").strip()
        if not raw or "BreadcrumbList" not in raw:
            continue
        try:
            import json

            data = json.loads(raw)
        except ValueError:
            continue
        for node in _walk_jsonld(data):
            if isinstance(node, dict) and node.get("@type") == "BreadcrumbList":
                for item in node.get("itemListElement", []) or []:
                    name = _ld_name(item)
                    url = _ld_url(item)
                    if name:
                        out.append({"name": name, "url": url or ""})
    if out:
        return out
    # Fall back to a breadcrumb ``nav`` or ``ol`` element.
    nav = soup.select_one("nav.breadcrumb, nav[aria-label*=breadcrumb i], ol.breadcrumb")
    if nav:
        for a in nav.find_all("a"):
            text = collapse_whitespace(a.get_text(" "))
            href = a.get("href")
            if text and href:
                with contextlib.suppress(ValueError):
                    out.append({"name": text, "url": urljoin(base_url, href.strip())})
    return out


def _walk_jsonld(node: Any) -> list[Any]:
    """Flatten an arbitrarily nested JSON-LD structure."""
    out: list[Any] = []
    stack = [node]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            out.append(cur)
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return out


def _ld_name(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    name = item.get("name")
    if isinstance(name, str) and name.strip():
        return collapse_whitespace(name)
    inner = item.get("item") if isinstance(item.get("item"), dict) else None
    if isinstance(inner, dict) and isinstance(inner.get("name"), str):
        return collapse_whitespace(inner["name"])
    return None


def _ld_url(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    for key in ("url", "item"):
        val = item.get(key)
        if isinstance(val, str):
            return val
        if isinstance(val, dict) and isinstance(val.get("@id"), str):
            return val["@id"]
    return None


def _same_as(soup: BeautifulSoup, base_url: str) -> list[str]:
    """Extract organization ``sameAs`` URLs from microdata and social links."""
    out: list[str] = []
    seen: set[str] = set()
    # Explicit ``itemprop="sameAs"`` is the strongest source.
    for tag in soup.select('[itemprop="sameAs"]'):
        href = (tag.get("href") or "").strip()
        if href and href not in seen:
            seen.add(href)
            out.append(href)
    # Supplement explicit values with recognized social-profile links.
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        try:
            host = (urlparse(href).hostname or "").lower()
        except ValueError:
            continue
        if not host:
            continue
        if any(host == s or host.endswith("." + s) for s in _SOCIAL_HOSTS) and href not in seen:
            seen.add(href)
            out.append(href)
    return out


def _microdata_prop(soup: BeautifulSoup, prop: str) -> str | None:
    """Read a microdata ``itemprop`` value as text."""
    tag = soup.select_one(f'[itemprop="{prop}"]')
    if not tag:
        return None
    # Structured ``content`` and ``href`` values take precedence over text.
    for attr in ("content", "href"):
        val = tag.get(attr)
        if val:
            return collapse_whitespace(val)
    text = collapse_whitespace(tag.get_text(" "))
    return text or None


def _microdata_in_scope(soup: BeautifulSoup, scope_re: str, prop: str) -> str | None:
    """Read ``itemprop`` only inside an ``itemscope`` matching ``scope_re``.

    Without scope awareness, ``itemprop="name"`` on a product page may capture the
    product name rather than the organization. This helper searches only the
    requested scope; callers may apply their own explicit fallback afterward.
    """
    for scope in soup.select(f'[itemtype*="{scope_re}"]'):
        tag = scope.select_one(f'[itemprop="{prop}"]')
        if tag:
            for attr in ("content", "href"):
                val = tag.get(attr)
                if val:
                    return collapse_whitespace(val)
            text = collapse_whitespace(tag.get_text(" "))
            if text:
                return text
    return None


def _organization(soup: BeautifulSoup, og: dict[str, str]) -> dict[str, Any]:
    """Extract organization name, logo, phone, and address from microdata and OG.

    Organization and LocalBusiness scopes are checked first to avoid capturing a
    product name; ``og:site_name`` and ``og:logo`` provide narrow fallbacks.
    """
    name = (
        _microdata_in_scope(soup, "Organization", "name")
        or _microdata_in_scope(soup, "LocalBusiness", "name")
        or collapse_whitespace(og.get("og:site_name"))
        or None
    )
    logo = None
    logo_meta = soup.find("meta", attrs={"property": "og:logo"}) or soup.find(
        "meta", attrs={"name": "og:logo"}
    )
    if logo_meta and logo_meta.get("content"):
        logo = collapse_whitespace(logo_meta["content"])
    if not logo:
        logo = _microdata_in_scope(soup, "Organization", "logo") or _microdata_in_scope(
            soup, "LocalBusiness", "logo"
        )
    return {
        "name": name,
        "logo": logo,
        "telephone": (
            _microdata_in_scope(soup, "Organization", "telephone")
            or _microdata_in_scope(soup, "LocalBusiness", "telephone")
        ),
        "address": (
            _microdata_in_scope(soup, "Organization", "address")
            or _microdata_in_scope(soup, "LocalBusiness", "address")
        ),
    }


def _price(soup: BeautifulSoup, text: str) -> dict[str, Any] | None:
    """Extract a price from microdata, then heuristically from visible text."""
    val = _microdata_prop(soup, "price")
    currency = _microdata_prop(soup, "priceCurrency")
    if val:
        return {
            "value": val,
            "currency": currency or None,
            "heuristic": False,
            "source": "microdata",
        }
    match = _PRICE_RE.search(text or "")
    if match:
        return {"value": match.group(0), "currency": None, "heuristic": True, "source": "text"}
    return None


def _rating(soup: BeautifulSoup, text: str) -> dict[str, Any] | None:
    """Extract a factual microdata rating or a heuristic ``4.5 out of 5`` match."""
    val = _microdata_prop(soup, "ratingValue")
    if val:
        return {
            "value": val,
            "count": _microdata_prop(soup, "reviewCount") or _microdata_prop(soup, "ratingCount"),
            "heuristic": False,
            "source": "microdata",
        }
    match = _RATING_RE.search(text or "")
    if match:
        return {"value": match.group(1), "count": None, "heuristic": True, "source": "text"}
    return None


def _types_from_jsonld(blocks: list[Any]) -> list[str]:
    """Extract existing JSON-LD ``@type`` values, the classifier's strongest signal."""
    types: list[str] = []
    for node in _walk_jsonld(blocks):
        if not isinstance(node, dict):
            continue
        raw = node.get("@type")
        if isinstance(raw, str):
            types.append(raw.rsplit("/", 1)[-1].rsplit(":", 1)[-1])
        elif isinstance(raw, list):
            types.extend(t.rsplit("/", 1)[-1].rsplit(":", 1)[-1] for t in raw if isinstance(t, str))
    # Deduplicate while preserving source order.
    seen: set[str] = set()
    uniq: list[str] = []
    for t in types:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def extract(html: str, url: str) -> dict[str, Any]:
    """Extract page facts from supplied HTML without network access.

    The flat result feeds both the page-type classifier and ``@graph`` generator.
    Fields remain ``None`` or empty when evidence is absent; explicit absence is
    preferable to an invented value.
    """
    base = parse_html(html, url)
    soup = BeautifulSoup(html, features="lxml")
    doc_base = document_base_url(soup, url)
    h1_list = base["headings"].get("h1") or []
    text = base["text"] or ""

    return {
        "url": url,
        "title": base["title"],
        "description": base["meta_description"],
        "canonical": base["canonical"],
        "og": base["og"],
        "twitter": base["twitter"],
        "h1": h1_list[0] if h1_list else None,
        "word_count": base["word_count"],
        "published_time": _article_time(soup),
        "modified_time": _article_time(soup, "article:modified_time"),
        "author_rel": _rel_author(soup),
        "breadcrumbs": _breadcrumbs(soup, doc_base),
        "same_as": _same_as(soup, doc_base),
        "organization": _organization(soup, base["og"]),
        "price": _price(soup, text),
        "rating": _rating(soup, text),
        "existing_jsonld": base["jsonld"],
        "existing_types": _types_from_jsonld(base["jsonld"]),
    }
