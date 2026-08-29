"""Detect whether a site returns a genuine 404 for a nonexistent URL.

A broken link discovered by a crawler appears in crawl exports. A soft 404 is
different: the server returns **200 OK** for a nonexistent URL, often with a
templated "nothing found" page. Search engines can treat these responses as
low-value pages eligible for indexing.

Screaming Frog does not detect this through a normal crawl because it requests
known URLs rather than inventing nonexistent ones. The check therefore needs
active probes, like the reconnaissance modules.

The algorithm creates two deterministic nonexistent URLs from the origin's
SHA-256 hash under ``/.well-known/``, a path unlikely to collide with real
content. Requests use the shared HTTP layer with redirects enabled because the
final status matters, not the first hop. Strict AND logic requires agreement:
two 2xx/3xx responses confirm a soft 404 (warning), two 404/410 responses pass,
and disagreement produces ``unknown`` without a verdict.
"""

from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import urlsplit, urlunsplit

PROBE_COUNT = 2


def probe_urls(start_url: str) -> list[str]:
    """Build deterministic nonexistent URLs from a site's origin.

    Hashing the origin yields the same pair on repeated runs, which is useful
    for report caching. The ``/.well-known/`` path is unlikely to overlap with
    real site content.
    """
    parts = urlsplit(start_url if "://" in start_url else "https://" + start_url)
    origin = urlunsplit((parts.scheme or "https", parts.netloc, "", "", ""))
    seed = hashlib.sha256(origin.encode()).hexdigest()[:12]
    return [f"{origin}/.well-known/seo-audit/not-found-{seed}-{i}" for i in (1, 2)]


def classify_soft404(probes: list[dict[str, Any]]) -> str:
    """Classify probes as ``pass``, ``warning`` (soft 404), or ``unknown``.

    Strict AND logic requires both probes to agree. Otherwise the result is
    ``unknown``: one 200 and one 404 response do not support a verdict.
    """
    conclusive = [p for p in probes if "status" in p and not p.get("access_blocked")]
    successful = [p for p in conclusive if 200 <= p["status"] < 400]
    correct_missing = [p for p in conclusive if p["status"] in (404, 410)]

    if len(conclusive) != PROBE_COUNT:
        return "unknown"
    if len(successful) == PROBE_COUNT:
        return "warning"  # both probes returned 2xx/3xx: soft 404 confirmed
    if len(correct_missing) == PROBE_COUNT:
        return "pass"  # both probes returned genuine 404/410 responses
    return "unknown"  # disagreement does not support a verdict


def check_soft404(url: str, timeout: float = 20.0) -> dict[str, Any]:
    """Request two probes and classify soft-404 behavior. Network boundary."""
    targets = probe_urls(url)
    try:
        from seohead.recon.net import http_client

        client, _ = http_client(timeout)
    except ImportError:
        return {"ok": False, "error": "httpx is required"}

    probes: list[dict[str, Any]] = []
    try:
        with client:
            for target in targets:
                try:
                    resp = client.get(target)
                    probes.append(
                        {
                            "url": target,
                            "status": resp.status_code,  # final status after automatic redirects
                            "final_url": str(resp.url),
                            "redirected": str(resp.url) != target,
                        }
                    )
                except Exception as exc:
                    probes.append({"url": target, "error": str(exc)})
    except Exception as exc:
        return {"ok": False, "url": url, "error": str(exc)}

    verdict = classify_soft404(probes)
    findings = {
        "pass": "the site returns genuine 404/410 responses for nonexistent URLs",
        "warning": (
            "soft 404: nonexistent URLs return 200/3xx responses and may create "
            "indexable low-value pages"
        ),
        "unknown": "the probes disagreed or did not complete; no verdict is available",
    }[verdict]
    return {
        "ok": True,
        "url": url,
        "verdict": verdict,
        "probes": probes,
        "findings": [findings],
    }
