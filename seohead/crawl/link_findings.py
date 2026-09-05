"""Security- and structure-shaped findings computed straight from a crawl's own evidence.

Sibling to ``linkgraph.py``: pure, and never imports ``seohead.sf``. Two findings here read
only what a crawl always records (``LinkEdge.destination``, ``.nofollow``, ``FormEdge``);
two need ``LinkEdge.rel``/``.target``/``.raw_href``, which only exist when the crawl was run
with ``link_attributes.capture`` on — see that setting's own docstring in
``crawl/spider.py`` for why it defaults off. Each such function is a plain filter over the
edge/form list; the caller (``seohead.servers.handlers``) decides when the data exists to ask.
"""

from __future__ import annotations

import ipaddress
from collections import defaultdict
from typing import Any
from urllib.parse import urlsplit

from seohead.crawl.spider import FormEdge, LinkEdge

# Reverse tabnabbing (the opened page gets a live handle to the opener via window.opener)
# is prevented by either token; a link naming just one is not a finding.
_SAFE_BLANK_REL = {"noopener", "noreferrer"}


def _is_localhost(host: str) -> bool:
    host = host.lower().rstrip(".")
    if not host:
        return False
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False  # not a literal IP -- an ordinary hostname, not localhost


def outlinks_to_localhost(links: list[LinkEdge]) -> list[dict[str, Any]]:
    """Edges pointing at a loopback address -- a dev/staging reference leaked into
    production markup. Needs only ``destination``, so it runs on every crawl."""
    out = []
    for edge in links:
        if _is_localhost(urlsplit(edge.destination).hostname or ""):
            out.append({"target_url": edge.source, "destination": edge.destination})
    return out


def unsafe_cross_origin_links(links: list[LinkEdge]) -> list[dict[str, Any]]:
    """``target="_blank"`` links naming neither ``noopener`` nor ``noreferrer`` in rel.

    Requires ``capture_attributes``: an edge whose attributes were never captured has
    ``target == ""`` and never matches, which is the correct "not measured" behaviour
    rather than a false positive or a false clean result.
    """
    out = []
    for edge in links:
        if edge.target.lower() != "_blank":
            continue
        if _SAFE_BLANK_REL & {t.lower() for t in edge.rel}:
            continue
        out.append({"target_url": edge.source, "destination": edge.destination})
    return out


def protocol_relative_links(links: list[LinkEdge]) -> list[dict[str, Any]]:
    """Edges whose href was written in the ``//host/path`` form before resolution.

    Also gated by ``capture_attributes``: ``raw_href`` is only populated when it is on.
    """
    out = []
    for edge in links:
        if edge.raw_href.startswith("//"):
            out.append(
                {
                    "target_url": edge.source,
                    "destination": edge.destination,
                    "raw_href": edge.raw_href,
                }
            )
    return out


def follow_and_nofollow_inlinks(links: list[LinkEdge], host: str) -> list[str]:
    """Internal destinations linked both with and without ``nofollow``.

    A page reached one way from some source and the other way from another is inconsistently
    signalled to a crawler about the same URL. Uses only ``destination``/``nofollow``, which
    are always recorded, so it needs no ``capture_attributes``.
    """
    host = host.lower()
    by_dest: dict[str, set[bool]] = defaultdict(set)
    for edge in links:
        if (urlsplit(edge.destination).hostname or "").lower() != host:
            continue
        by_dest[edge.destination].add(edge.nofollow)
    return sorted(dest for dest, flags in by_dest.items() if flags == {True, False})


def form_url_insecure(forms: list[FormEdge]) -> list[dict[str, Any]]:
    """Forms whose action submits over plain HTTP, regardless of the hosting page's own
    scheme -- data leaves the browser unencrypted the moment the form is submitted."""
    return [
        {"target_url": f.page, "action": f.action, "method": f.method}
        for f in forms
        if f.action.lower().startswith("http://")
    ]


def forms_on_http_pages_with_password(forms: list[FormEdge]) -> list[dict[str, Any]]:
    """Password forms served from a plain-HTTP page: the credentials themselves travel
    unencrypted to reach the form, before the action URL is ever involved."""
    return [
        {"target_url": f.page, "action": f.action}
        for f in forms
        if f.has_password and f.page.lower().startswith("http://")
    ]
