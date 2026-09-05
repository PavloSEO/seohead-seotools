"""Chrome UX Report (CrUX): Core Web Vitals as real users experienced them.

Issue #59 deliberately implements only the Lighthouse audits computable without a browser trace
and forbids synthesising a Performance score. CrUX is the honest way to report the metrics that
need one: not synthesised, not lab, measured on real Chrome visits at origin or URL level. It
turns ``SLOW_RESPONSE`` from "the server took a while for us" into "users experience this as
slow" (issue #97).

**This is a credential-gated skeleton, not an exercised client.** CrUX needs a Google Cloud API
key; nothing in this environment can obtain or verify one. Parsing is built and tested against a
recorded response shape, but the request has never reached the live API. A missing key returns
an explicit, truthful failure — never a fabricated result.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

HOST = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"
TIMEOUT = 30

# payload, api key -> response body text
Fetcher = Callable[[dict[str, Any], str], str]


def _default_fetcher(payload: dict[str, Any], api_key: str) -> str:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        HOST,
        data=data,
        method="POST",
        # The key travels in a header, never in the query string, so it can never end up
        # echoed into a URL that lands in a log line or an exception message.
        headers={"Content-Type": "application/json", "X-goog-api-key": api_key},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # nosec B310
        return response.read().decode("utf-8")


def _api_error(exc: urllib.error.HTTPError) -> str:
    try:
        body = json.loads(exc.read().decode("utf-8", "replace"))
        return str(body.get("error", {}).get("message") or exc.reason)
    except ValueError:
        return str(exc.reason)


def query(
    *,
    url: str | None = None,
    origin: str | None = None,
    form_factor: str | None = None,
    metrics: list[str] | None = None,
    api_key: str | None = None,
    fetcher: Fetcher | None = None,
) -> dict[str, Any]:
    """Return field Core Web Vitals for a URL or an entire origin, at the 75th percentile.

    CrUX reports at either level, never both at once: pass exactly one of ``url``/``origin``.
    A target with too little real-user traffic to be reported is not an error — CrUX returns
    ``NOT_FOUND`` for it, which comes back here as ``ok: true`` with an empty ``metrics``.
    """
    from seohead.data_sources.credentials import MissingCredential, crux_api_key

    if bool(url) == bool(origin):
        raise ValueError("exactly one of url or origin is required")
    try:
        key = api_key or crux_api_key()
    except MissingCredential as exc:
        return {"ok": False, "error": str(exc)}

    payload: dict[str, Any] = {"url": url} if url else {"origin": origin}
    if form_factor:
        payload["formFactor"] = form_factor
    if metrics:
        payload["metrics"] = metrics

    fetch = fetcher or _default_fetcher
    try:
        raw = fetch(payload, key)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"ok": True, "target": url or origin, "metrics": {}, "note": "no CrUX data"}
        return {"ok": False, "error": _api_error(exc), "status": exc.code}
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"ok": False, "error": f"CrUX request failed: {exc}"}

    body = json.loads(raw) if raw.strip() else {}
    record = body.get("record") or {}
    metric_data = record.get("metrics") or {}
    return {
        "ok": True,
        "target": url or origin,
        "form_factor": (record.get("key") or {}).get("formFactor"),
        "collection_period": record.get("collectionPeriod"),
        "metrics": {
            name: {"p75": (values.get("percentiles") or {}).get("p75")}
            for name, values in metric_data.items()
        },
    }
