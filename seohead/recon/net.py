"""Shared network layer: URL guardrails, DNS-over-HTTPS, and RDAP.

Every user-controlled HTTP request should use :func:`http_client`. Request hooks
validate the initial URL and every redirect before a socket is opened. Private,
loopback, link-local, multicast, reserved, and otherwise non-global addresses are
blocked by default. Authorized staging and intranet work requires an explicit
``SEOHEAD_ALLOW_PRIVATE_NETWORKS=1`` opt-in.

DNS and registration checks use HTTP APIs because ``dig`` and ``whois`` are not
available in every container. A system ``whois`` binary remains an optional ccTLD
fallback. Network failures are returned as unavailable data rather than escaping
as fatal exceptions.
"""

from __future__ import annotations

import ipaddress
import os
import re
import shutil
import socket
import subprocess
from typing import Any
from urllib.parse import urljoin, urlsplit

UA = "Mozilla/5.0 (compatible; SEOHEAD-Tools/3.0; +https://seohead.tech/seotools)"
PRIVATE_NETWORK_ENV = "SEOHEAD_ALLOW_PRIVATE_NETWORKS"

DOH_ENDPOINTS = (
    "https://cloudflare-dns.com/dns-query",
    "https://dns.google/resolve",
)
RDAP_BOOTSTRAP = "https://rdap.org"

_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))*"
    r"\.(?!-)[a-z0-9-]*[a-z][a-z0-9-]*(?<!-)$"
)


class NetworkUnavailable(RuntimeError):
    """Raised internally when the base HTTP client is unavailable."""


def private_networks_enabled() -> bool:
    """Return whether private-network access was explicitly enabled."""
    return os.getenv(PRIVATE_NETWORK_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _is_public_address(value: str) -> bool:
    try:
        return ipaddress.ip_address(value.split("%", 1)[0]).is_global
    except ValueError:
        return False


def resolve_socket_addresses(host: str, port: int) -> list[tuple[int, int, int, Any]]:
    """Resolve once and return vetted socket addresses for a direct connection."""
    try:
        records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"hostname could not be resolved safely: {host}") from exc
    if not records:
        raise ValueError(f"hostname could not be resolved safely: {host}")
    if not private_networks_enabled() and any(
        not _is_public_address(record[4][0]) for record in records
    ):
        raise ValueError(
            f"private or non-public network target blocked; set {PRIVATE_NETWORK_ENV}=1 "
            "only for an authorized target"
        )

    unique: list[tuple[int, int, int, Any]] = []
    seen: set[tuple[int, int, int, Any]] = set()
    for family, socktype, proto, _canonname, sockaddr in records:
        item = (family, socktype, proto, sockaddr)
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def validate_url(url: str) -> str:
    """Validate an HTTP(S) URL and block private networks by default.

    Embedded credentials are rejected because they are easily copied into logs and
    transcripts. Hostnames are resolved before a request and every resolved address
    must be globally routable. This is a guardrail, not a network sandbox; callers
    handling hostile DNS should additionally isolate the process or container.
    """
    value = str(url or "").strip()
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise ValueError(f"invalid URL: {exc}") from exc
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("only http:// and https:// URLs are supported")
    if not parsed.hostname:
        raise ValueError("URL must include a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("embedded URL credentials are not supported")

    if private_networks_enabled():
        return value

    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost"):
        raise ValueError(
            f"private-network target blocked; set {PRIVATE_NETWORK_ENV}=1 "
            "only for an authorized target"
        )

    resolve_socket_addresses(
        host,
        parsed.port or (443 if parsed.scheme.lower() == "https" else 80),
    )
    return value


def _guard_request(request: Any) -> None:
    validate_url(str(request.url))


def _guard_redirect(response: Any) -> None:
    if not getattr(response, "is_redirect", False):
        return
    location = response.headers.get("location")
    if location:
        validate_url(urljoin(str(response.request.url), location))


def network_event_hooks() -> dict[str, list[Any]]:
    """Return httpx hooks that validate every request and redirect."""
    return {"request": [_guard_request], "response": [_guard_redirect]}


def http_client(timeout: float, **kwargs: Any):
    """Return ``(client, http2_capable)`` with shared URL guardrails.

    The boolean must reach reports: without the optional HTTP/2 codec, reporting
    HTTP/1.1 as a server limitation would describe the client rather than the site.
    """
    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - a base dependency
        raise NetworkUnavailable("httpx is required") from exc

    supplied_hooks = kwargs.pop("event_hooks", None) or {}
    hooks = network_event_hooks()
    for phase, values in supplied_hooks.items():
        hooks.setdefault(phase, []).extend(values)

    options = {
        "timeout": timeout,
        "headers": {"User-Agent": UA},
        "follow_redirects": True,
        "event_hooks": hooks,
        **kwargs,
    }
    try:
        return httpx.Client(http2=True, **options), True
    except ImportError:
        return httpx.Client(**options), False


def _client(timeout: float):
    return http_client(timeout)[0]


def normalize_domain(value: str) -> str:
    """Normalize a URL or hostname to a lowercase, non-www ASCII domain."""
    raw = (value or "").strip()
    if not raw:
        return ""
    if "//" in raw:
        raw = urlsplit(raw).netloc or urlsplit(raw).path
    raw = raw.split("/")[0].split("@")[-1].strip().rstrip(".").lower()
    if raw.startswith("[") or raw.count(":") > 1:
        return ""
    raw = raw.split(":")[0]
    raw = raw.removeprefix("www.")
    try:
        raw = raw.encode("idna").decode("ascii")
    except (UnicodeError, UnicodeDecodeError):
        return ""
    return raw if _DOMAIN_RE.match(raw) else ""


def normalize_url(value: str) -> str:
    """Normalize user input to an absolute HTTP(S) URL without touching DNS."""
    raw = (value or "").strip()
    if not raw:
        return ""
    scheme_prefix = raw.split(":", 1)[0].lower()
    if "//" not in raw and scheme_prefix.isalpha() and raw[len(scheme_prefix) :].startswith(":"):
        return ""
    if "//" not in raw:
        raw = "https://" + raw
    try:
        parts = urlsplit(raw)
    except ValueError:
        return ""
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return ""
    if parts.username is not None or parts.password is not None:
        return ""
    return raw


def doh(name: str, rtype: str, timeout: float = 8.0) -> list[str]:
    """Query DNS over HTTPS and return record values; failures return an empty list."""
    if not name:
        return []
    try:
        client = _client(timeout)
    except NetworkUnavailable:
        return []
    with client:
        for endpoint in DOH_ENDPOINTS:
            try:
                response = client.get(
                    endpoint,
                    params={"name": name, "type": rtype},
                    headers={"Accept": "application/dns-json"},
                )
                if response.status_code != 200:
                    continue
                answers = response.json().get("Answer") or []
            except Exception:
                continue
            records = []
            for item in answers:
                data = str(item.get("data", "")).strip()
                if data:
                    records.append(data.strip('"').rstrip("."))
            if records:
                return records
    return []


def rdap(path: str, timeout: float = 12.0) -> dict[str, Any]:
    """Query RDAP and distinguish unsupported registries from parser failures."""
    try:
        client = _client(timeout)
    except NetworkUnavailable:
        return {"supported": False, "error": "httpx is required"}
    with client:
        try:
            response = client.get(
                f"{RDAP_BOOTSTRAP}/{path}",
                headers={"Accept": "application/rdap+json"},
            )
        except Exception as exc:
            return {"supported": False, "error": str(exc)}
        if response.status_code == 404:
            return {"supported": False, "error": "not found in RDAP"}
        if response.status_code >= 400:
            return {"supported": False, "error": f"RDAP HTTP {response.status_code}"}
        try:
            return {"supported": True, "data": response.json()}
        except ValueError:
            return {"supported": False, "error": "RDAP returned non-JSON"}


def whois_text(domain: str, timeout: float = 15.0) -> str | None:
    """Return raw system-whois output as an optional ccTLD fallback."""
    binary = shutil.which("whois")
    if not binary or not domain:
        return None
    try:
        process = subprocess.run(
            [binary, domain],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    return process.stdout or None
