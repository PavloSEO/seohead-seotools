"""Google Search Console: what Google itself observed, not what a crawl inferred.

This is the biggest gap the free-sources issue names (#97). A crawl says what a page *is*; only
Search Console says whether Google indexed it, what it ranks for, and its own indexing verdict
for a single URL. Two operations cover that:

* ``search_analytics`` — clicks, impressions, average position, and CTR per query/page, for an
  own, verified property.
* ``inspect_url`` — the URL Inspection endpoint's indexing verdict for one URL.

**This is a credential-gated skeleton, not an exercised client.** Search Console requires OAuth
against a verified property; nothing in this environment can obtain or verify that. Both
functions parse a real response shape against recorded fixtures, but neither has been run
against the live API. A missing token returns an explicit, truthful failure — see
``credentials.gsc_access_token`` — never a fabricated or synthesized result.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

SEARCH_ANALYTICS_HOST = "https://www.googleapis.com/webmasters/v3"
INSPECTION_HOST = "https://searchconsole.googleapis.com/v1"
TIMEOUT = 30

# payload, bearer token -> response body text
Fetcher = Callable[[dict[str, Any], str], str]


def _default_fetcher(url: str) -> Fetcher:
    def fetch(payload: dict[str, Any], token: str) -> str:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        # The request URL is the fixed HTTPS Search Console endpoint; the token travels in a
        # header, never in the URL, so it cannot end up echoed into a log line or a stack trace.
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # nosec B310
            return response.read().decode("utf-8")

    return fetch


def _api_error(exc: urllib.error.HTTPError) -> str:
    try:
        body = json.loads(exc.read().decode("utf-8", "replace"))
        return str(body.get("error", {}).get("message") or exc.reason)
    except ValueError:
        return str(exc.reason)


def _response_object(raw: str) -> dict[str, Any] | None:
    try:
        body = json.loads(raw) if raw.strip() else {}
    except (AttributeError, ValueError):
        return None
    return body if isinstance(body, dict) else None


def search_analytics(
    site_url: str,
    *,
    start_date: str,
    end_date: str,
    dimensions: list[str] | None = None,
    row_limit: int = 1000,
    token: str | None = None,
    fetcher: Fetcher | None = None,
) -> dict[str, Any]:
    """Query rows a verified property earned in search, by query, page, country, or device."""
    from seohead.data_sources.credentials import MissingCredential, gsc_access_token

    if not site_url:
        raise ValueError("site_url required")
    try:
        bearer = token or gsc_access_token()
    except MissingCredential as exc:
        return {"ok": False, "error": str(exc)}

    url = f"{SEARCH_ANALYTICS_HOST}/sites/{urllib.parse.quote(site_url, safe='')}/searchAnalytics/query"
    payload = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": dimensions or ["query"],
        "rowLimit": row_limit,
    }
    fetch = fetcher or _default_fetcher(url)
    try:
        raw = fetch(payload, bearer)
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": _api_error(exc), "status": exc.code}
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"ok": False, "error": f"Search Console request failed: {exc}"}

    body = _response_object(raw)
    if body is None:
        return {"ok": False, "error": "Search Console malformed response"}
    if "rows" not in body:
        rows = []
    else:
        rows = body["rows"]
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            return {"ok": False, "error": "Search Console malformed response"}
    return {
        "ok": True,
        "site_url": site_url,
        "period": f"{start_date}..{end_date}",
        "count": len(rows),
        "rows": [
            {
                "keys": r.get("keys"),
                "clicks": r.get("clicks"),
                "impressions": r.get("impressions"),
                "ctr": r.get("ctr"),
                "position": r.get("position"),
            }
            for r in rows
        ],
    }


def inspect_url(
    site_url: str,
    inspection_url: str,
    *,
    token: str | None = None,
    fetcher: Fetcher | None = None,
) -> dict[str, Any]:
    """Google's own indexing verdict for one URL: indexed or not, and why."""
    from seohead.data_sources.credentials import MissingCredential, gsc_access_token

    if not site_url or not inspection_url:
        raise ValueError("site_url and inspection_url required")
    try:
        bearer = token or gsc_access_token()
    except MissingCredential as exc:
        return {"ok": False, "error": str(exc)}

    url = f"{INSPECTION_HOST}/urlInspection/index:inspect"
    payload = {"inspectionUrl": inspection_url, "siteUrl": site_url}
    fetch = fetcher or _default_fetcher(url)
    try:
        raw = fetch(payload, bearer)
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": _api_error(exc), "status": exc.code}
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"ok": False, "error": f"Search Console request failed: {exc}"}

    body = _response_object(raw)
    if body is None:
        return {"ok": False, "error": "Search Console malformed response"}
    inspection = body.get("inspectionResult")
    if not isinstance(inspection, dict):
        return {"ok": False, "error": "Search Console malformed response"}
    index_status = inspection.get("indexStatusResult")
    if index_status is None:
        index_status = {}
    if not isinstance(index_status, dict):
        return {"ok": False, "error": "Search Console malformed response"}
    return {
        "ok": True,
        "site_url": site_url,
        "inspection_url": inspection_url,
        "verdict": index_status.get("verdict"),
        "coverage_state": index_status.get("coverageState"),
        "indexing_state": index_status.get("indexingState"),
        "last_crawl_time": index_status.get("lastCrawlTime"),
        "google_canonical": index_status.get("googleCanonical"),
        "user_canonical": index_status.get("userCanonical"),
    }
