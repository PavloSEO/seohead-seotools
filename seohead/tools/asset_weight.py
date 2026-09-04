"""CSS/JS weight and delivery analysis.

Fetches a page, discovers its linked stylesheets and scripts, fetches each of
them, and reports the checks that are answerable from bytes on the wire and
static markup — no rendering required:

* minification (a whitespace-ratio / line-length heuristic)
* render-blocking ``<script>``/``<link rel=stylesheet>`` in ``<head>``
* oversized individual files (configurable threshold)
* duplicate libraries bundled more than once, by content hash of the
  whitespace-stripped source (not by filename)
* compression (``Content-Encoding``) and cache lifetime (``Cache-Control``)
* ``@font-face`` blocks missing ``font-display: swap`` (or an equivalent value)
* legacy transpiled/polyfilled JS shipped unconditionally (a heuristic)

Two checks from the issue this module answers are deliberately NOT attempted
here and are reported under ``skipped`` rather than silently passing:

* **unused CSS/JS** — telling "loaded" from "used" needs a rendered DOM
  (coverage-style analysis), which this static-fetch tool does not have;
* **per-site bundle-size outliers** — needs more than one page. Once a caller
  has run :func:`analyze_page_asset_weight` over several pages, feed the
  resulting ``total_bytes`` values to :func:`flag_outlier_pages`.

Public API:
    analyze_page_asset_weight(url, **options) -> dict
    flag_outlier_pages(page_totals) -> list[str]
"""

from __future__ import annotations

import hashlib
import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from statistics import median
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from seohead.recon.net import UA, http_client
from seohead.tools.parser import document_base_url

DEFAULT_TIMEOUT = 15.0
# The issue's own suggested threshold for a single oversized file.
DEFAULT_FILE_SIZE_THRESHOLD_BYTES = 500_000
# Bounds one page's own fetch fan-out: a page linking hundreds of resources
# (often third-party trackers, not the site's own delivery problem) should not
# turn one audit call into an unbounded crawl.
MAX_RESOURCES = 60
DEFAULT_CONCURRENCY = 6

# Below this, a Cache-Control max-age is not "long-lived" for a static asset:
# a hashed/versioned filename can safely be cached far longer than an HTML
# page, so a short TTL here is a missed easy win rather than a correctness bug.
LONG_CACHE_SECONDS = 7 * 24 * 3600

_COMPRESSED_ENCODINGS = {"gzip", "br", "deflate", "zstd"}
_MAX_AGE_RE = re.compile(r"max-age\s*=\s*(\d+)", re.IGNORECASE)
_FONT_FACE_RE = re.compile(r"@font-face\s*\{([^}]*)\}", re.IGNORECASE | re.DOTALL)
_FONT_DISPLAY_OK_RE = re.compile(r"font-display\s*:\s*(swap|fallback|optional)", re.IGNORECASE)
# core-js/babel helpers are the standard marker a bundler leaves behind when it
# shipped transpiled/polyfilled code; a hand-rolled Object.assign shim is the
# same intent without a named library.
_LEGACY_JS_RE = re.compile(
    r"core-js|regeneratorRuntime|_babelPolyfill|@babel/runtime|Object\.assign\s*=\s*function"
)
_WHITESPACE_RE = re.compile(r"\s+")


# ── pure checks (no network) ────────────────────────────────────────────────


def whitespace_ratio(text: str) -> float:
    """Fraction of ``text`` that is whitespace."""
    if not text:
        return 0.0
    return sum(1 for c in text if c.isspace()) / len(text)


def looks_minified(text: str) -> bool:
    """Heuristic: minified CSS/JS reads as long lines with little whitespace.

    Hand-authored code is reformatted onto many short, indented lines, which
    pushes the whitespace ratio well above this line and the average line
    length well below it. A round-trip through a real minifier would be exact
    but adds a build-tool dependency for a signal this heuristic already gets
    right on both fixtures the acceptance criteria describe.
    """
    stripped = text.strip()
    if len(stripped) < 200:  # too small to carry a meaningful signal either way
        return True
    lines = stripped.splitlines() or [stripped]
    avg_line_length = len(stripped) / len(lines)
    return whitespace_ratio(stripped) < 0.15 and avg_line_length > 200


def content_hash(text: str) -> str:
    """SHA-256 of ``text`` with all whitespace removed.

    Whitespace-only reformatting (a different line-wrap width, a trailing
    newline) must not hide that two files bundle the same library, and must
    not manufacture a "duplicate" out of two files that only look alike.
    """
    normalized = _WHITESPACE_RE.sub("", text)
    return hashlib.sha256(normalized.encode("utf-8", "ignore")).hexdigest()


def find_duplicate_libraries(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group fetched resources of the same kind by content hash.

    A group is reported only when it spans more than one distinct URL —
    the same file linked twice is not a duplicate library, it is one file.
    """
    by_key: dict[tuple[str, str], list[str]] = {}
    for res in resources:
        if not res.get("ok") or not res.get("text"):
            continue
        key = (res.get("kind", ""), content_hash(res["text"]))
        by_key.setdefault(key, []).append(res["url"])

    out = []
    for (kind, digest), urls in sorted(by_key.items()):
        unique = sorted(set(urls))
        if len(unique) > 1:
            out.append({"kind": kind, "hash": digest, "urls": unique})
    return out


def is_render_blocking(tag_name: str, attrs: dict[str, Any]) -> bool:
    """Whether one ``<script>``/``<link>`` tag blocks first paint as written.

    A script is blocking unless it opts out: ``async``/``defer``, or a
    ``type`` the spec already defers (``module``) or that never executes as a
    classic script (``application/json`` and similar data islands).
    A stylesheet link is blocking unless ``media`` restricts it to a
    condition the initial render does not need, such as ``print``.
    """
    if tag_name == "script":
        if "async" in attrs or "defer" in attrs:
            return False
        script_type = str(attrs.get("type") or "").lower().strip()
        return script_type in ("", "text/javascript", "application/javascript")
    if tag_name == "link":
        media = str(attrs.get("media") or "").strip().lower()
        return media in ("", "all", "screen")
    return False


def find_render_blocking_resources(soup: BeautifulSoup, base_url: str) -> list[dict[str, Any]]:
    """Render-blocking ``<script src>`` / ``<link rel=stylesheet>`` in ``<head>``."""
    head = soup.head
    if head is None:
        return []
    out = []
    for tag in head.find_all("script"):
        src = tag.get("src")
        if src and is_render_blocking("script", tag.attrs):
            out.append({"url": urljoin(base_url, src), "tag": "script"})
    for tag in head.find_all("link"):
        rels = tag.get("rel") or []
        rels = [rels] if isinstance(rels, str) else rels
        href = tag.get("href")
        if (
            href
            and "stylesheet" in [r.lower() for r in rels]
            and is_render_blocking("link", tag.attrs)
        ):
            out.append({"url": urljoin(base_url, href), "tag": "link"})
    return out


def find_missing_font_display(css_text: str) -> list[dict[str, str]]:
    """``@font-face`` blocks without ``font-display: swap`` (or an equivalent)."""
    out = []
    for block in _FONT_FACE_RE.findall(css_text or ""):
        if not _FONT_DISPLAY_OK_RE.search(block):
            out.append({"excerpt": block.strip()[:200]})
    return out


def looks_legacy_transpiled(js_text: str) -> bool:
    """Whether ``js_text`` carries a transpiler/polyfill marker (a heuristic, not proof)."""
    return bool(_LEGACY_JS_RE.search(js_text or ""))


def check_cache_lifetime(cache_control: str | None) -> dict[str, Any]:
    """Whether a static asset's ``Cache-Control`` is long-lived."""
    value = cache_control or ""
    lowered = value.lower()
    if "no-store" in lowered or "no-cache" in lowered:
        return {"ok": False, "max_age": 0, "reason": "no-store/no-cache on a static asset"}
    match = _MAX_AGE_RE.search(value)
    max_age = int(match.group(1)) if match else None
    if max_age is None:
        return {"ok": False, "max_age": None, "reason": "no Cache-Control max-age"}
    if "immutable" in lowered or max_age >= LONG_CACHE_SECONDS:
        return {"ok": True, "max_age": max_age, "reason": None}
    return {"ok": False, "max_age": max_age, "reason": "max-age is short for a static asset"}


def check_compression(content_encoding: str | None) -> dict[str, Any]:
    """Whether a resource was served compressed."""
    value = (content_encoding or "").strip().lower()
    return {"ok": value in _COMPRESSED_ENCODINGS, "encoding": value or None}


def flag_outlier_pages(
    page_totals: dict[str, int], *, multiple: float = 2.0, min_bytes: int = 100_000
) -> list[str]:
    """Pages whose total CSS+JS payload dwarfs the site's median.

    ``min_bytes`` guards a templated site of near-identical pages from having
    every page above the median called an outlier over a few stray bytes —
    the same failure mode ``check_html_weight`` guards against for whole-page
    size (see ``seohead/sf/core/heuristics.py``).
    """
    sizes = list(page_totals.values())
    if len(sizes) < 2:
        return []
    baseline = median(sizes) or 1
    return sorted(
        url
        for url, total in page_totals.items()
        if total > baseline * multiple and total - baseline > min_bytes
    )


# ── fetch + orchestrate ──────────────────────────────────────────────────────


def _discover_resources(soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
    """External ``<link rel=stylesheet>`` and ``<script src>`` URLs, deduplicated."""
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for tag in soup.find_all("link"):
        rels = tag.get("rel") or []
        rels = [rels] if isinstance(rels, str) else rels
        href = tag.get("href")
        if href and "stylesheet" in [r.lower() for r in rels]:
            url = urljoin(base_url, href.strip())
            if url not in seen:
                seen.add(url)
                out.append({"url": url, "kind": "css"})
    for tag in soup.find_all("script"):
        src = tag.get("src")
        if src:
            url = urljoin(base_url, src.strip())
            if url not in seen:
                seen.add(url)
                out.append({"url": url, "kind": "js"})
    return out


def analyze_page_asset_weight(
    url: str,
    *,
    file_size_threshold: int = DEFAULT_FILE_SIZE_THRESHOLD_BYTES,
    max_resources: int = MAX_RESOURCES,
    concurrency: int = DEFAULT_CONCURRENCY,
    timeout: float = DEFAULT_TIMEOUT,
    fetcher=None,
) -> dict[str, Any]:
    """Fetch ``url`` and its linked CSS/JS, and run every static-analysis check.

    ``fetcher``, when given, replaces the network client with a callable
    ``fetcher(resource_url) -> response``; a response needs only ``.status_code``,
    ``.content`` (or ``.text``), and ``.headers``. This is how tests exercise the
    whole pipeline without a socket.
    """
    client = nullcontext()
    if fetcher is None:
        client, _http2_capable = http_client(timeout, headers={"User-Agent": UA})

    def fetch_one(target: dict[str, str]) -> dict[str, Any]:
        try:
            resp = fetcher(target["url"]) if fetcher else client.get(target["url"])
        except Exception as exc:
            return {**target, "ok": False, "error": str(exc)}
        content = getattr(resp, "content", None)
        text = resp.text if hasattr(resp, "text") else (content or b"").decode("utf-8", "ignore")
        # Decoded size: what the browser parses and executes, which is what a
        # minification/bloat check cares about, not the compressed wire size.
        size = len(content) if content is not None else len(text.encode("utf-8"))
        headers = getattr(resp, "headers", {}) or {}
        return {
            **target,
            "ok": resp.status_code < 400,
            "status_code": resp.status_code,
            "bytes": size,
            "text": text,
            "cache_control": headers.get("cache-control"),
            "content_encoding": headers.get("content-encoding"),
        }

    with client:
        try:
            page_resp = fetcher(url) if fetcher else client.get(url)
        except Exception as exc:
            return {"ok": False, "url": url, "error": str(exc)}
        if page_resp.status_code >= 400:
            return {"ok": False, "url": url, "status_code": page_resp.status_code}

        final_url = str(getattr(page_resp, "url", url) or url)
        soup = BeautifulSoup(page_resp.text, features="lxml")
        base_url = document_base_url(soup, final_url)

        render_blocking = find_render_blocking_resources(soup, base_url)
        targets = _discover_resources(soup, base_url)
        truncated = len(targets) > max_resources
        targets = targets[:max_resources]

        if not targets:
            resources: list[dict[str, Any]] = []
        elif fetcher is not None:
            # A caller-supplied fetcher (tests, a plain dict lookup) is not
            # promised to be thread-safe.
            resources = [fetch_one(t) for t in targets]
        else:
            workers = max(1, min(int(concurrency), 10, len(targets)))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                resources = list(pool.map(fetch_one, targets))

    oversized = [
        {"url": r["url"], "bytes": r["bytes"], "threshold": file_size_threshold}
        for r in resources
        if r.get("ok") and r["bytes"] > file_size_threshold
    ]
    duplicates = find_duplicate_libraries(resources)

    unminified, missing_font_display, legacy_js, cache_findings, compression_findings = (
        [],
        [],
        [],
        [],
        [],
    )
    for res in resources:
        if not res.get("ok"):
            continue
        if not looks_minified(res["text"]):
            unminified.append(res["url"])
        if res["kind"] == "css":
            missing_font_display += [
                {"source": res["url"], **f} for f in find_missing_font_display(res["text"])
            ]
        elif looks_legacy_transpiled(res["text"]):
            legacy_js.append(res["url"])
        cache = check_cache_lifetime(res.get("cache_control"))
        if not cache["ok"]:
            cache_findings.append({"url": res["url"], **cache})
        compression = check_compression(res.get("content_encoding"))
        if not compression["ok"]:
            compression_findings.append({"url": res["url"], **compression})

    # Inline <style> blocks carry the same font-display risk as an external
    # stylesheet, at zero fetch cost.
    for style_tag in soup.find_all("style"):
        missing_font_display += [
            {"source": "inline", **f} for f in find_missing_font_display(style_tag.get_text())
        ]

    total_bytes = sum(r["bytes"] for r in resources if r.get("ok"))
    findings = []
    if render_blocking:
        findings.append(f"{len(render_blocking)} render-blocking resource(s) in <head>")
    if oversized:
        findings.append(f"{len(oversized)} file(s) over the {file_size_threshold}-byte threshold")
    if duplicates:
        findings.append(f"{len(duplicates)} library bundled more than once")
    if unminified:
        findings.append(f"{len(unminified)} file(s) do not look minified")
    if missing_font_display:
        findings.append(f"{len(missing_font_display)} @font-face block(s) without font-display")
    if legacy_js:
        findings.append(f"{len(legacy_js)} script(s) look like unconditional legacy/polyfill code")
    if cache_findings:
        findings.append(f"{len(cache_findings)} resource(s) without a long-lived Cache-Control")
    if compression_findings:
        findings.append(f"{len(compression_findings)} resource(s) served uncompressed")

    return {
        "ok": True,
        "url": url,
        "final_url": final_url,
        "resources": resources,
        "resources_truncated": truncated,
        "total_bytes": total_bytes,
        "render_blocking": render_blocking,
        "oversized": oversized,
        "duplicate_libraries": duplicates,
        "unminified": unminified,
        "missing_font_display": missing_font_display,
        "legacy_js": legacy_js,
        "cache_findings": cache_findings,
        "compression_findings": compression_findings,
        "findings": findings,
        "skipped": [
            {
                "check": "unused_css_js",
                "reason": "needs a rendered DOM to tell loaded from used (tracked in #18)",
            },
            {
                "check": "site_median_outlier",
                "reason": "needs more than one page; call flag_outlier_pages() with each "
                "page's total_bytes",
            },
        ],
    }
