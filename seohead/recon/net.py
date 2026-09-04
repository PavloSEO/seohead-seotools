"""Shared network layer: URL guardrails, DNS-over-HTTPS, and RDAP.

Every user-controlled HTTP request should use :func:`http_client`. Request hooks
validate the initial URL and every redirect before a socket is opened. Private,
loopback, link-local, multicast, reserved, and otherwise non-global addresses are
blocked by default. Authorized staging and intranet work requires an explicit
``SEOHEAD_ALLOW_PRIVATE_NETWORKS=1`` opt-in — that opens every private range, for
a run that genuinely needs it. ``SEOHEAD_ALLOW_PRIVATE_HOSTS`` is the scoped
alternative: a comma-separated list of exact hostnames (e.g. one staging box)
allowed to resolve privately without opening the rest of RFC 1918 space.

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
from urllib.parse import urljoin, urlsplit, urlunsplit

UA = "Mozilla/5.0 (compatible; SEOHEAD-Tools/3.0; +https://seohead.tech/seotools)"
PRIVATE_NETWORK_ENV = "SEOHEAD_ALLOW_PRIVATE_NETWORKS"
PRIVATE_HOST_ALLOWLIST_ENV = "SEOHEAD_ALLOW_PRIVATE_HOSTS"

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


def allowed_private_hosts() -> frozenset[str]:
    """Hostnames explicitly permitted to resolve to a non-public address.

    A scoped alternative to :data:`PRIVATE_NETWORK_ENV`: it authorizes one
    named staging host without opening every private range. Matching is exact
    on the lowercased, dot-stripped hostname — an entry does not extend to a
    subdomain, to a different host a redirect points at, or to any other
    address the same staging host might expose under a different name.
    """
    raw = os.getenv(PRIVATE_HOST_ALLOWLIST_ENV, "")
    return frozenset(host.strip().rstrip(".").lower() for host in raw.split(",") if host.strip())


def _private_target_allowed(host: str) -> bool:
    """Whether ``host`` may resolve to a private or otherwise non-public address."""
    return private_networks_enabled() or (host or "").rstrip(".").lower() in allowed_private_hosts()


# Ranges that carry a non-public address inside a globally-scoped one. Python's
# ``is_global`` answers a question about the address family, not about where the
# packet ends up: 64:ff9b::7f00:1 is 127.0.0.1 wrapped in the well-known NAT64
# prefix and reports is_global=True, so on any NAT64 host — common in CI and in
# mobile and cloud networks — the guard would pass a request to loopback.
_TRANSLATED_PREFIXES = tuple(
    ipaddress.ip_network(cidr)
    for cidr in (
        "64:ff9b::/96",  # RFC 6052 well-known NAT64 prefix
        "64:ff9b:1::/48",  # RFC 8215 local-use NAT64
        "2002::/16",  # 6to4, embeds an IPv4 address
        "::ffff:0:0/96",  # IPv4-mapped
        "::/96",  # IPv4-compatible, deprecated but still parsed
    )
)


def _embedded_ipv4(address: ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    """The IPv4 address a translated IPv6 address actually reaches."""
    packed = address.packed
    if address in _TRANSLATED_PREFIXES[2]:  # 6to4 carries it in bytes 2..6
        return ipaddress.IPv4Address(packed[2:6])
    return ipaddress.IPv4Address(packed[-4:])


def _is_public_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return False
    # Translated forms are checked first: the wrapper's own scope says nothing
    # about the destination, and Python scores some of them non-global and
    # others global regardless of what they carry.
    if isinstance(address, ipaddress.IPv6Address) and any(
        address in prefix for prefix in _TRANSLATED_PREFIXES
    ):
        try:
            return _embedded_ipv4(address).is_global
        except (ipaddress.AddressValueError, ValueError):
            return False
    return address.is_global


def pinned_target(url: str) -> tuple[str, dict[str, str], dict[str, str]]:
    """Rewrite a URL to connect to a vetted address, keeping the hostname.

    ``validate_url`` resolved DNS and then threw the answer away, so the HTTP
    client resolved a second time and connected to whatever came back. That is a
    time-of-check-to-time-of-use gap: a hostile resolver can answer the check
    with a public address and the connection with a loopback one. Since the guard
    also runs per redirect hop, it was one window per hop rather than one.

    Returns the URL to request, headers carrying the original ``Host``, and the
    request extensions carrying the hostname for SNI — so certificate
    verification still happens against the name, not the address.
    """
    parts = urlsplit(url)
    host = parts.hostname
    if not host:
        raise ValueError(f"no host to pin in {url!r}")
    port = parts.port or (443 if parts.scheme == "https" else 80)

    address = resolve_socket_addresses(host, port)[0][3][0].split("%", 1)[0]
    literal = f"[{address}]" if ":" in address else address
    netloc = f"{literal}:{parts.port}" if parts.port else literal
    pinned = urlunsplit((parts.scheme, netloc, parts.path or "/", parts.query, ""))

    authority = f"{host}:{parts.port}" if parts.port else host
    return pinned, {"Host": authority}, {"sni_hostname": host}


def resolve_socket_addresses(host: str, port: int) -> list[tuple[int, int, int, Any]]:
    """Resolve once and return vetted socket addresses for a direct connection."""
    try:
        records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"hostname could not be resolved safely: {host}") from exc
    if not records:
        raise ValueError(f"hostname could not be resolved safely: {host}")
    if not _private_target_allowed(host) and any(
        not _is_public_address(record[4][0]) for record in records
    ):
        raise ValueError(
            f"private or non-public network target blocked; set {PRIVATE_NETWORK_ENV}=1 "
            f"to authorize every private target, or add {host!r} to "
            f"{PRIVATE_HOST_ALLOWLIST_ENV} to authorize only this one"
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
    if (host == "localhost" or host.endswith(".localhost")) and host not in allowed_private_hosts():
        raise ValueError(
            f"private-network target blocked; set {PRIVATE_NETWORK_ENV}=1 to authorize "
            f"every private target, or add {host!r} to {PRIVATE_HOST_ALLOWLIST_ENV} to "
            "authorize only this one"
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


# Compound public suffixes common enough that treating the last two labels as
# the registrable domain would merge unrelated sites. A full public suffix list
# is large and changes; this only has to tell a subdomain from a separate site.
_COMPOUND_SUFFIXES = frozenset({"com", "net", "org", "co", "gov", "edu", "ac", "spb", "msk"})


def registrable_domain(host: str) -> str:
    """Approximate the registrable domain of a hostname."""
    host = (host or "").lower().strip(".")
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    if parts[-2] in _COMPOUND_SUFFIXES and len(parts[-1]) <= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


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


# Registries the default whois resolver does not reach. Without these it answers
# with the zone record instead of the domain's own, which reads as a real
# registration: every .ru domain came back with the .RU delegation date of 1994.
WHOIS_SERVERS_BY_TLD: dict[str, str] = {
    "ru": "whois.tcinet.ru",
    "su": "whois.tcinet.ru",
    "xn--p1ai": "whois.tcinet.ru",  # the Cyrillic .rf ccTLD, in punycode
}

# Fields a registry uses to refer to the authoritative server.
_WHOIS_REFERRAL_KEYS = ("whois", "refer", "registrar whois server")

_HOSTNAME_RE = re.compile(
    r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$"
)


def _whois_field(text: str, keys: tuple[str, ...]) -> str | None:
    """First value of the first matching key, ignoring comment lines."""
    for line in text.splitlines():
        stripped = line.lstrip()
        if ":" not in stripped or stripped.startswith(("%", "#")):
            continue
        key, _, value = stripped.partition(":")
        if key.strip().lower() in keys and value.strip():
            return value.strip()
    return None


def whois_text(domain: str, timeout: float = 15.0, server: str | None = None) -> str | None:
    """Return raw system-whois output as an optional ccTLD fallback."""
    binary = shutil.which("whois")
    if not binary or not domain:
        return None
    argv = [binary]
    if server:
        # The server may come from a registry response, i.e. untrusted input.
        # Only a syntactically valid hostname is ever passed on, and it is
        # passed as an argument vector, never through a shell.
        if not _HOSTNAME_RE.match(server.lower()):
            return None
        argv += ["-h", server]
    argv.append(domain)
    try:
        process = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    except (subprocess.SubprocessError, OSError):
        return None
    return process.stdout or None


def whois_lookup(domain: str, timeout: float = 15.0) -> tuple[str | None, str | None]:
    """Query whois, following one registry referral. Returns ``(text, server)``.

    The referral hop is what separates a domain's own record from the record of
    its zone; a caller still has to confirm the answer is about the domain it
    asked for.
    """
    if not domain:
        return None, None
    tld = domain.rsplit(".", 1)[-1].lower()
    mapped = WHOIS_SERVERS_BY_TLD.get(tld)
    if mapped:
        text = whois_text(domain, timeout, server=mapped)
        if text:
            return text, mapped

    text = whois_text(domain, timeout)
    if not text:
        return None, None

    referral = _whois_field(text, _WHOIS_REFERRAL_KEYS)
    if referral:
        referral = referral.split("//")[-1].split("/")[0].strip().lower()
        if referral and referral != (mapped or ""):
            deeper = whois_text(domain, timeout, server=referral)
            if deeper:
                return deeper, referral
    return text, None
