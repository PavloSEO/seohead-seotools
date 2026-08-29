"""hreflang extractor + validator.

Pulls ``<link rel="alternate" hreflang="...">`` annotations from a page and runs
basic validity checks: x-default presence, self-reference, duplicate langs, and
obviously malformed language codes.
"""

from __future__ import annotations

import re

from seohead.recon.net import http_client

_UA = "Mozilla/5.0 (compatible; SEOHEAD-Tools/3.0; +https://seohead.tech/seotools)"
# ISO 639-1 lang optionally + region, or the literal x-default.
_LANG_RE = re.compile(r"^(x-default|[a-z]{2,3}(-[A-Za-z]{2,4})?)$")


def extract_hreflang(html: str, base_url: str = "") -> list[dict]:
    """Pure extraction of hreflang alternates from HTML (no network)."""
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, features="lxml")
    out: list[dict] = []
    for link in soup.find_all("link"):
        rel = " ".join(link.get("rel", [])).lower() if link.get("rel") else ""
        hreflang = link.get("hreflang")
        if "alternate" in rel and hreflang:
            href = link.get("href", "")
            out.append(
                {"hreflang": hreflang, "href": urljoin(base_url, href) if base_url else href}
            )
    return out


def validate(alternates: list[dict], page_url: str = "") -> list[str]:
    issues: list[str] = []
    langs = [a["hreflang"] for a in alternates]
    if not alternates:
        return ["no hreflang annotations found"]
    for lang in langs:
        if not _LANG_RE.match(lang):
            issues.append(f"malformed hreflang code: {lang!r}")
    dupes = {lang for lang in langs if langs.count(lang) > 1}
    for lang in dupes:
        issues.append(f"duplicate hreflang: {lang}")
    if "x-default" not in langs:
        issues.append("no x-default alternate")
    hrefs = {a["href"] for a in alternates}
    if page_url and page_url not in hrefs:
        issues.append("page does not self-reference in its hreflang set")
    return issues


def check_hreflang(url: str, timeout: float = 25.0) -> dict:
    try:
        client, _http2_capable = http_client(
            timeout, follow_redirects=True, headers={"User-Agent": _UA}
        )
        with client:
            resp = client.get(url)
    except Exception as exc:
        return {"ok": False, "url": url, "error": str(exc)}
    final_url = str(resp.url)
    alternates = extract_hreflang(resp.text, final_url)
    return {
        "ok": True,
        "url": url,
        "final_url": final_url,
        "count": len(alternates),
        "alternates": alternates,
        "issues": validate(alternates, final_url),
    }


if __name__ == "__main__":
    html = (
        '<link rel="alternate" hreflang="ru" href="/ru">'
        '<link rel="alternate" hreflang="en-US" href="/en">'
        '<link rel="alternate" hreflang="x-default" href="/">'
    )
    alts = extract_hreflang(html, "https://x.tld")
    assert len(alts) == 3 and alts[0]["href"] == "https://x.tld/ru"
    assert validate(alts, "https://x.tld/ru") == []
    assert "no x-default alternate" in validate(alts[:1], "")
    print("OK: hreflang self-check passed")
