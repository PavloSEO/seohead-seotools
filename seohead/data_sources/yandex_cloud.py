"""Yandex Cloud Search API client for Wordstat demand and Yandex Web SERPs.

Two Cloud Search API v2 services run at ``searchapi.api.cloud.yandex.net``; these are not the
legacy Direct API:

* ``/v2/wordstat/topRequests`` expands a phrase and returns related queries with base volume;
* ``/v2/wordstat/dynamics`` returns seasonality;
* ``/v2/web/searchAsync`` plus operation polling returns Yandex SERPs.

**Cost.** Both services are metered. At the first public snapshot, Wordstat GetTop and
GetDynamics cost ₽20 per 1,000 requests, while GetRegionsTree is free. Yandex
Web Search costs substantially less through asynchronous requests than through synchronous
requests. This client intentionally implements only the asynchronous endpoint. Provider prices
can change; confirm the current tariff before a large run.

**Quota, not price, is the primary ceiling.** Wordstat allows 100 requests per hour and 10
requests per second; asynchronous Web Search allows 35,000 per hour. The client backs off on HTTP
429 and 503. The API does not expose remaining quota, which is visible only in the billing
console, so usage is tracked in the local spend ledger.

**Wordstat does not provide exact-match volume.** Operators such as ``!``, ``+``, and ``[]`` are
unsupported, and ``count`` is base volume that can be roughly nine times higher than exact
volume. Use Arsenkin for exact values. Multiple regions in one request **sum** volume; query each
region separately when per-region values are required.
"""

from __future__ import annotations

import base64
import json
import re
import ssl
import time
import urllib.error
import urllib.request
from typing import Any

from seohead.data_sources import spend
from seohead.data_sources.credentials import yandex_cloud_api_key, yandex_cloud_folder_id

HOST = "https://searchapi.api.cloud.yandex.net"
OPERATIONS = "https://operation.api.cloud.yandex.net/operations"
SOURCE = "yandex_cloud"


def normalize(phrase: str) -> str:
    """Canonicalize spacing and case, including the required Russian yo-to-ye fold."""
    return re.sub(r"\s+", " ", (phrase or "").strip().lower().replace("ё", "е"))  # noqa: RUF001


class _Base:
    def __init__(self, api_key: str | None = None, folder_id: str | None = None, rps: float = 5):
        self.key = api_key or yandex_cloud_api_key()
        self.folder = folder_id or yandex_cloud_folder_id()
        self.min_interval = 1.0 / rps
        self._last = 0.0
        try:
            import certifi

            self.context = ssl.create_default_context(cafile=certifi.where())
        except Exception:  # certifi is optional; the default SSL context is valid.
            self.context = ssl.create_default_context()

    def _request(
        self, url: str, body: dict | None = None, method: str = "POST", retries: int = 5
    ) -> tuple[int, Any]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Authorization": f"Api-Key {self.key}"}
        if data is not None:
            headers["Content-Type"] = "application/json"

        last: tuple[int, Any] = (0, "no request was completed")
        for attempt in range(retries):
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            request = urllib.request.Request(url, data=data, method=method, headers=headers)
            try:
                # The request URL is built from the fixed HTTPS provider base.
                with urllib.request.urlopen(  # nosec B310
                    request, timeout=45, context=self.context
                ) as response:
                    return response.status, json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode("utf-8", "replace")
                if exc.code in (429, 500, 503):  # Quota or transient failure: back off and retry.
                    time.sleep(2**attempt + 1)
                    last = (exc.code, raw)
                    continue
                return exc.code, _maybe_json(raw)
            except (ssl.SSLError, urllib.error.URLError) as exc:
                time.sleep(2**attempt + 1)
                last = (0, f"network: {exc}")
                continue
        return last


def _maybe_json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except ValueError:
        return {"raw": raw}


class Wordstat(_Base):
    """Wordstat demand client for phrase expansion, related queries, and seasonality."""

    def top(self, phrase: str, limit: int = 300, regions=("225",), devices=("DEVICE_ALL",)) -> dict:
        status, body = self._request(
            f"{HOST}/v2/wordstat/topRequests",
            {
                "phrase": phrase,
                "numPhrases": int(limit),
                "folderId": self.folder,
                "regions": list(regions),
                "devices": list(devices),
            },
        )
        spend.record(
            SOURCE,
            "wordstat.topRequests",
            cost=1,
            unit="requests",
            items=1,
            extra={"phrase": phrase, "regions": list(regions)},
        )
        if status != 200:
            raise RuntimeError(f"topRequests {status}: {body}")
        return body

    def dynamics(
        self,
        phrase: str,
        from_date: str,
        to_date: str,
        period: str = "PERIOD_MONTHLY",
        regions=("225",),
        devices=("DEVICE_ALL",),
    ) -> dict:
        """Return seasonality; dates use RFC 3339, for example ``2026-01-01T00:00:00Z``."""
        status, body = self._request(
            f"{HOST}/v2/wordstat/dynamics",
            {
                "phrase": phrase,
                "folderId": self.folder,
                "period": period,
                "fromDate": from_date,
                "toDate": to_date,
                "regions": list(regions),
                "devices": list(devices),
            },
        )
        spend.record(
            SOURCE,
            "wordstat.dynamics",
            cost=1,
            unit="requests",
            items=1,
            extra={"phrase": phrase, "period": period},
        )
        if status != 200:
            raise RuntimeError(f"dynamics {status}: {body}")
        return body

    def expand(
        self, phrase: str, limit: int = 300, regions=("225",), devices=("DEVICE_ALL",)
    ) -> tuple[dict[str, int], dict]:
        """Expand a phrase into ``({phrase: base_volume}, metadata)``.

        Both Wordstat columns are retained: ``results`` is the left column of phrase refinements,
        with up to 2,000 entries, and ``associations`` is the right column of up to 20 related
        queries. Associations can be broadly noisy, but they are an important source of synonyms
        for large semantic cores. Filter them by meaning instead of discarding the column.
        """
        body = self.top(phrase, limit, regions, devices)
        pool: dict[str, int] = {}
        origin: dict[str, str] = {}
        for tag in ("results", "associations"):
            for item in body.get(tag) or []:
                key = normalize(item.get("phrase"))
                if not key:
                    continue
                try:
                    count = int(item.get("count") or 0)
                except (TypeError, ValueError):
                    count = 0
                if count >= pool.get(key, -1):
                    pool[key] = count
                origin.setdefault(key, tag)
        return pool, {
            "totalCount": body.get("totalCount"),
            "results": len(body.get("results") or []),
            "associations": len(body.get("associations") or []),
            "origin": origin,
        }


class WebSearch(_Base):
    """Yandex SERP client using async-only requests; synchronous search costs 16 times more."""

    def search(
        self,
        query: str,
        region: str = "225",
        search_type: str = "SEARCH_TYPE_RU",
        groups: int = 10,
        docs_in_group: int = 1,
        family: str = "FAMILY_MODE_NONE",
        timeout: int = 120,
    ) -> dict:
        status, operation = self._request(
            f"{HOST}/v2/web/searchAsync",
            _serp_body(query, region, search_type, groups, docs_in_group, family, self.folder),
        )
        spend.record(
            SOURCE,
            "web.searchAsync",
            cost=1,
            unit="requests",
            items=1,
            extra={"query": query, "region": region},
        )
        if status != 200:
            raise RuntimeError(f"searchAsync {status}: {operation}")

        operation_id = operation.get("id")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(5)
            _, done = self._request(f"{OPERATIONS}/{operation_id}", method="GET")
            if isinstance(done, dict) and done.get("done"):
                if done.get("error"):
                    raise RuntimeError(f"operation returned an error: {done['error']}")
                raw = (done.get("response") or {}).get("rawData")
                xml = base64.b64decode(raw).decode("utf-8", "replace") if raw else ""
                return {"operation_id": operation_id, "xml": xml, "docs": parse_serp(xml)}
        raise RuntimeError(f"operation {operation_id} did not finish within {timeout}s")

    def search_batch(
        self,
        queries: list[str],
        region: str = "225",
        search_type: str = "SEARCH_TYPE_RU",
        groups: int = 10,
        docs_in_group: int = 1,
        family: str = "FAMILY_MODE_NONE",
        timeout: int = 300,
        poll: int = 4,
    ) -> dict[str, dict]:
        """Run several queries as one concurrently processed batch.

        All operations are submitted first and then polled together. The service processes async
        operations concurrently, so N queries take approximately one batch duration instead of
        the sum of individual durations. Operations unfinished at ``timeout`` are omitted from
        the returned mapping, but they have already been charged and their ``operation_id``
        remains available in the spend ledger.
        """
        pending: dict[str, str] = {}
        for query in queries:
            status, operation = self._request(
                f"{HOST}/v2/web/searchAsync",
                _serp_body(query, region, search_type, groups, docs_in_group, family, self.folder),
            )
            if status == 200 and isinstance(operation, dict) and operation.get("id"):
                pending[operation["id"]] = query
        spend.record(
            SOURCE,
            "web.searchAsync",
            cost=len(pending),
            unit="requests",
            items=len(queries),
            extra={"region": region, "batch": True},
        )

        results: dict[str, dict] = {}
        deadline = time.monotonic() + timeout
        while pending and time.monotonic() < deadline:
            time.sleep(poll)
            for operation_id, query in list(pending.items()):
                _, done = self._request(f"{OPERATIONS}/{operation_id}", method="GET")
                if not isinstance(done, dict) or not done.get("done"):
                    continue  # Still running, or a transient polling failure.
                del pending[operation_id]
                if done.get("error"):
                    results[query] = {"error": done["error"], "docs": []}
                    continue
                raw = (done.get("response") or {}).get("rawData")
                xml = base64.b64decode(raw).decode("utf-8", "replace") if raw else ""
                results[query] = {"operation_id": operation_id, "xml": xml, "docs": parse_serp(xml)}
        return results


def _serp_body(
    query: str,
    region: str,
    search_type: str,
    groups: int,
    docs_in_group: int,
    family: str,
    folder: str,
) -> dict:
    return {
        "query": {"searchType": search_type, "queryText": query, "familyMode": family, "page": "0"},
        "groupSpec": {
            "groupMode": "GROUP_MODE_DEEP",
            "groupsOnPage": str(groups),
            "docsInGroup": str(docs_in_group),
        },
        "region": str(region),
        "l10N": "LOCALIZATION_RU",
        "folderId": folder,
        "responseFormat": "FORMAT_XML",
    }


def parse_serp(xml: str) -> list[dict]:
    """Parse Yandex SERP XML into ``[{pos, url, domain, title}]``."""
    docs = []
    for position, match in enumerate(re.finditer(r"<doc[ >].*?</doc>", xml, re.DOTALL), 1):
        block = match.group(0)
        url_match = re.search(r"<url>(.*?)</url>", block, re.DOTALL)
        title_match = re.search(r"<title>(.*?)</title>", block, re.DOTALL)
        domain_match = re.search(r"<domain>(.*?)</domain>", block, re.DOTALL)
        url = re.sub(r"<.*?>", "", url_match.group(1)).strip() if url_match else ""
        docs.append(
            {
                "pos": position,
                "url": url,
                "domain": domain_match.group(1).strip() if domain_match else _host(url),
                "title": re.sub(r"<.*?>", "", title_match.group(1)).strip() if title_match else "",
            }
        )
    return docs


def _host(url: str) -> str:
    match = re.search(r"https?://([^/]+)", url or "")
    return match.group(1).replace("www.", "") if match else ""
