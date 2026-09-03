"""Compare raw server HTML with the rendered DOM seen after JavaScript executes.

A search crawler receives the server response, while a browser user may see a
different document after client-side scripts run. This check measures that gap.
Google can render JavaScript, but rendering is deferred and not guaranteed;
Yandex has more limited rendering; many AI crawlers do not render at all. A page
looking complete in a browser therefore does not prove that its source response
contains indexable content and links.

Performance values are laboratory measurements only: LCP, CLS, and timing data
from one run on one machine. They are not field Core Web Vitals from the Chrome
UX Report and are explicitly returned under ``metrics_lab``.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from seohead.recon.net import http_client, normalize_url, validate_url

# Common single-page application shells. An empty mount container means the raw
# response exposes no application content to a crawler that does not render.
_SHELL_IDS = ("root", "app", "__next", "__nuxt", "q-app", "main-app")

# Below this word threshold, the raw response is effectively empty without
# JavaScript and warrants a dedicated finding.
EMPTY_BODY_WORDS = 50

# The sole all-clear message also determines ``js_dependent``. Keeping it in one
# constant prevents the summary and findings from drifting apart.
ALL_CLEAR = (
    "Raw HTML and rendered DOM are materially equivalent; JavaScript "
    "rendering does not determine SEO-visible content"
)

_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style|noscript)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL
)
_TAG_RE = re.compile(r"<[^>]+>")


def _guard_browser_route(route) -> None:
    """Block browser subrequests that escape the public-network boundary."""
    request_url = route.request.url
    if request_url.startswith(("about:", "blob:", "data:")):
        route.continue_()
        return
    try:
        validate_url(request_url)
    except ValueError:
        route.abort("blockedbyclient")
        return
    route.continue_()


# This script reads laboratory metrics after load. LCP and CLS are captured by
# PerformanceObserver; the remaining values come from Navigation Timing.
_METRICS_JS = """() => {
  const nav = performance.getEntriesByType('navigation')[0] || {};
  const lcpEntries = performance.getEntriesByType('largest-contentful-paint') || [];
  const paints = {};
  for (const p of performance.getEntriesByType('paint')) paints[p.name] = Math.round(p.startTime);
  return {
    ttfb_ms: Math.round(nav.responseStart || 0),
    dom_content_loaded_ms: Math.round(nav.domContentLoadedEventEnd || 0),
    load_ms: Math.round(nav.loadEventEnd || 0),
    first_contentful_paint_ms: paints['first-contentful-paint'] ?? null,
    largest_contentful_paint_ms: window.__seohead_lcp
      ? Math.round(window.__seohead_lcp)
      : (lcpEntries.length ? Math.round(lcpEntries[lcpEntries.length - 1].startTime) : null),
    cumulative_layout_shift: window.__seohead_cls != null
      ? Math.round(window.__seohead_cls * 1000) / 1000 : null,
    transfer_size_kb: nav.transferSize ? Math.round(nav.transferSize / 1024) : null,
  };
}"""

# CLS and LCP accumulate from navigation start, so observers must be installed
# before navigation. Installing them afterward misses the earliest and often
# largest shifts. LCP also requires a buffered observer in practice because
# ``getEntriesByType('largest-contentful-paint')`` is commonly empty; relying on
# that API alone produced null LCP values in real-site runs.
_CLS_INIT_JS = """
window.__seohead_cls = 0;
window.__seohead_lcp = 0;
try {
  new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      if (!entry.hadRecentInput) window.__seohead_cls += entry.value;
    }
  }).observe({type: 'layout-shift', buffered: true});
} catch (e) {}
try {
  new PerformanceObserver((list) => {
    const entries = list.getEntries();
    if (entries.length) window.__seohead_lcp = entries[entries.length - 1].startTime;
  }).observe({type: 'largest-contentful-paint', buffered: true});
} catch (e) {}
"""


def _visible_text(html: str) -> str:
    """Return candidate content text after removing scripts, styles, and tags."""
    return _TAG_RE.sub(" ", _SCRIPT_STYLE_RE.sub(" ", html or ""))


def _words(html: str) -> int:
    return len([w for w in _visible_text(html).split() if len(w) > 1])


def _links(html: str, base_url: str) -> set[str]:
    """Return internal links that can participate in crawling the site."""
    if not html:
        return set()
    from seohead.tools.parser import document_base_url

    # Host comes from the page URL; links resolve against the document base.
    host = urlparse(normalize_url(base_url)).hostname or ""
    resolve_from = document_base_url(html, base_url)
    out: set[str] = set()
    for href in re.findall(r'<a\b[^>]*href=["\']([^"\']+)', html, re.IGNORECASE):
        href = href.strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        absolute = urljoin(resolve_from, href).split("#")[0]
        if (urlparse(absolute).hostname or "") == host:
            out.add(absolute)
    return out


def _jsonld_types(html: str) -> list[str]:
    """Extract Schema.org JSON-LD types.

    Markup injected only after JavaScript does not exist for non-rendering
    crawlers, so raw and rendered type sets are measured separately.
    """
    types: list[str] = []
    for block in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html or "",
        re.IGNORECASE | re.DOTALL,
    ):
        try:
            data = json.loads(block.strip())
        except (ValueError, TypeError):
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                t = node.get("@type")
                if isinstance(t, str):
                    types.append(t)
                elif isinstance(t, list):
                    types += [x for x in t if isinstance(x, str)]
                stack += [v for v in node.values() if isinstance(v, (dict, list))]
            elif isinstance(node, list):
                stack += node
    return sorted(set(types))


def _empty_shell(html: str) -> str | None:
    """Return the ID of an empty SPA mount container, or ``None``."""
    for shell_id in _SHELL_IDS:
        m = re.search(
            rf'<div[^>]+id=["\']{shell_id}["\'][^>]*>(.*?)</div>',
            html or "",
            re.IGNORECASE | re.DOTALL,
        )
        if m and not m.group(1).strip():
            return shell_id
        if re.search(
            rf'<div[^>]+id=["\']{shell_id}["\'][^>]*/?>\s*</div>', html or "", re.IGNORECASE
        ):
            return shell_id
    return None


def _snapshot(html: str, url: str) -> dict[str, Any]:
    """Build an identical, comparable snapshot for raw HTML and rendered DOM."""
    from seohead.tools.page_facts import extract

    facts = extract(html, url) if html else {}
    return {
        "words": _words(html),
        "links": len(_links(html, url)),
        "title": facts.get("title") or "",
        "h1": facts.get("h1") or "",
        "canonical": facts.get("canonical") or "",
        "jsonld_types": _jsonld_types(html),
        "html_bytes": len(html or ""),
    }


def compare(
    raw: dict[str, Any], rendered: dict[str, Any], raw_html: str = "", shell: str | None = None
) -> list[str]:
    """Generate findings for a raw-HTML and rendered-DOM snapshot pair.

    This pure function uses neither the network nor a browser, allowing complete
    offline tests while the Playwright layer remains a thin adapter.
    """
    out: list[str] = []

    if shell:
        out.append(
            f'Raw HTML contains an empty <div id="{shell}"> mount point; the '
            "page is assembled entirely by JavaScript, so a non-rendering "
            "crawler receives an empty page"
        )
    elif raw.get("words", 0) < EMPTY_BODY_WORDS < rendered.get("words", 0):
        out.append(
            f"Raw HTML contains {raw['words']} words versus "
            f"{rendered['words']} after rendering; the server response "
            "contains effectively no page copy"
        )

    words_gain = rendered.get("words", 0) - raw.get("words", 0)
    if raw.get("words", 0) >= EMPTY_BODY_WORDS and words_gain > 0:
        share = words_gain / max(rendered.get("words", 1), 1)
        if share >= 0.3:
            out.append(
                f"{share:.0%} of page copy appears only after JavaScript "
                f"(+{words_gain} words); this content is unavailable to "
                "non-rendering crawlers"
            )

    links_gain = rendered.get("links", 0) - raw.get("links", 0)
    if links_gain > 0 and rendered.get("links", 0):
        share = links_gain / rendered["links"]
        if share >= 0.3 or raw.get("links", 0) == 0:
            out.append(
                f"{links_gain} of {rendered['links']} internal links appear "
                "only after JavaScript, reducing or preventing crawl discovery"
            )

    if raw.get("title") != rendered.get("title"):
        out.append(
            f"The title changes after JavaScript: raw {raw.get('title')!r}, "
            f"rendered {rendered.get('title')!r}; crawlers may index "
            "different title values"
        )
    if raw.get("h1") != rendered.get("h1") and rendered.get("h1"):
        out.append(
            f"H1 differs between raw HTML {raw.get('h1') or '—'!r} and rendered DOM "
            f"{rendered.get('h1')!r}"
        )
    if raw.get("canonical") != rendered.get("canonical"):
        out.append(
            "The canonical URL is injected or changed by JavaScript; this "
            "indexing directive should not depend on rendering"
        )

    new_types = set(rendered.get("jsonld_types", [])) - set(raw.get("jsonld_types", []))
    if new_types:
        out.append("Schema.org types appear only after JavaScript: " + ", ".join(sorted(new_types)))

    if not out:
        out.append(ALL_CLEAR)
    return out


def render_check(
    url: str, timeout: float = 30.0, wait: str = "load", viewport: str = "desktop"
) -> dict[str, Any]:
    """Compare a server response with the DOM produced after JavaScript executes.

    Playwright is optional. When unavailable, the tool returns ``ok: False`` and
    an installation command instead of misrepresenting an unperformed check.

    ``wait="load"`` is deliberate. ``networkidle`` may never occur on commercial
    sites because analytics, chat, and advertising keep connections open, turning
    a useful render check into a timeout. Search-engine rendering does not require
    complete network silence either. Callers may still request ``networkidle``
    when a particular application genuinely needs it.
    """
    if not url or not str(url).strip():
        return {"ok": False, "error": "URL is required"}
    target = normalize_url(str(url).strip())

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "ok": False,
            "error": "Playwright is required",
            "install": "pip install 'seohead[render]' && python -m playwright install chromium",
        }
    try:
        validate_url(target)
    except ValueError as exc:
        return {"ok": False, "url": target, "error": str(exc)}

    # Fetch raw HTML with the regular client: this is what a non-rendering crawler receives.
    client, _ = http_client(timeout)
    try:
        resp = client.get(target)
        raw_html = resp.text
        final_url = str(resp.url)
        status = resp.status_code
    except Exception as exc:
        return {
            "ok": False,
            "error": f"Raw HTML fetch failed: {type(exc).__name__}: {exc}",
            "url": target,
        }
    finally:
        client.close()

    size = {"width": 390, "height": 844} if viewport == "mobile" else {"width": 1366, "height": 768}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                context = browser.new_context(viewport=size, is_mobile=(viewport == "mobile"))
                context.add_init_script(_CLS_INIT_JS)
                page = context.new_page()
                page.route("**/*", _guard_browser_route)
                page.goto(target, wait_until=wait, timeout=timeout * 1000)
                rendered_html = page.content()
                rendered_url = page.url
                metrics = page.evaluate(_METRICS_JS)
            finally:
                browser.close()
    except Exception as exc:
        return {
            "ok": False,
            "error": f"Browser rendering failed: {type(exc).__name__}: {exc}",
            "url": target,
            "raw": _snapshot(raw_html, final_url),
        }

    raw = _snapshot(raw_html, final_url)
    rendered = _snapshot(rendered_html, rendered_url)
    shell = _empty_shell(raw_html)
    findings = compare(raw, rendered, raw_html, shell)
    return {
        "ok": True,
        "url": target,
        "final_url": final_url,
        "status": status,
        "viewport": viewport,
        "raw": raw,
        "rendered": rendered,
        "empty_shell": shell,
        # Keep the summary aligned with findings: five widget words do not make a
        # page JavaScript-dependent, while findings use a 30% materiality threshold.
        "js_dependent": findings != [ALL_CLEAR],
        # Laboratory, not field data: one run from one machine. Field Core Web
        # Vitals come from CrUX and must not be inferred from this measurement.
        "metrics_lab": metrics,
        "findings": findings,
    }


def rendered_html(url: str, timeout: float = 30.0, wait: str = "load") -> dict[str, Any]:
    """Return rendered HTML for tools that require the final DOM.

    A separate narrow function lets regional and similar audits request one HTML
    document without constructing the full raw-versus-rendered comparison report.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "ok": False,
            "error": "Playwright is required",
            "install": "pip install 'seohead[render]' && python -m playwright install chromium",
        }
    target = normalize_url(str(url or "").strip())
    if not target:
        return {"ok": False, "error": "URL is required"}
    try:
        validate_url(target)
    except ValueError as exc:
        return {"ok": False, "url": target, "error": str(exc)}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                page = browser.new_page()
                page.route("**/*", _guard_browser_route)
                page.goto(target, wait_until=wait, timeout=timeout * 1000)
                return {"ok": True, "url": page.url, "html": page.content()}
            finally:
                browser.close()
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "url": target}
