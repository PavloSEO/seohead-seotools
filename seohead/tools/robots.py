"""robots.txt fetcher + analyzer.

Fetches a site's robots.txt, parses user-agent groups (Allow/Disallow), lists the
declared sitemaps, and can test whether specific paths are crawlable for a UA.
"""

from __future__ import annotations

import contextlib
import re
from urllib.parse import urlparse, urlsplit

from seohead.recon.net import http_client

_UA = "Mozilla/5.0 (compatible; SEOHEAD-Tools/3.0; +https://seohead.tech/seotools)"


def _robots_url(url: str) -> str:
    p = urlparse(url if "://" in url else "https://" + url)
    return f"{p.scheme}://{p.netloc}/robots.txt"


def parse_robots(text: str) -> dict:
    """Pure parse of robots.txt content into groups + sitemaps (no network)."""
    groups: list[dict] = []
    sitemaps: list[str] = []
    current: dict | None = None
    # Crawl-delay was parsed by nobody, so a site asking to be crawled slowly was
    # crawled at whatever rate the operator chose.
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()
        if field == "user-agent":
            if current is None or current.get("_has_rules"):
                current = {
                    "user_agents": [],
                    "allow": [],
                    "disallow": [],
                    "crawl_delay": None,
                    "_has_rules": False,
                }
                groups.append(current)
            current["user_agents"].append(value)
        elif field in ("allow", "disallow") and current is not None:
            current[field].append(value)
            current["_has_rules"] = True
        elif field == "crawl-delay" and current is not None:
            # A malformed delay is no delay, not a crash.
            with contextlib.suppress(ValueError):
                current["crawl_delay"] = float(value.replace(",", "."))
        elif field == "sitemap":
            sitemaps.append(value)
    for g in groups:
        g.pop("_has_rules", None)
    return {"groups": groups, "sitemaps": sitemaps}


EMPTY_GROUP = {"allow": [], "disallow": [], "crawl_delay": None}


def _rules_for(parsed: dict, user_agent: str) -> dict:
    """The single group that applies, by longest matching product token.

    RFC 9309 selects the most specific match, and exactly one group applies.
    Taking the *last* match instead meant file order decided the outcome, and
    matching by substring meant a group naming a browser engine captured any
    agent whose string happened to contain it.
    """
    ua = user_agent.lower()
    best: dict | None = None
    best_length = -1
    star: dict | None = None
    for group in parsed["groups"]:
        for token in (u.lower().strip() for u in group["user_agents"]):
            if token == "*":
                if star is None:
                    star = group
                continue
            # A token matches when the agent name starts with it; "Googlebot"
            # applies to "Googlebot-Image", but not the other way round.
            if (ua == token or ua.startswith(token)) and len(token) > best_length:
                best, best_length = group, len(token)
    return best or star or dict(EMPTY_GROUP)


def crawl_delay(parsed: dict, user_agent: str = "*") -> float | None:
    """The delay the site asks this agent to keep, if it states one."""
    return _rules_for(parsed, user_agent).get("crawl_delay")


def _pattern_to_regex(pattern: str) -> re.Pattern:
    """Google robots pattern -> regex: ``*`` is any sequence, trailing ``$`` anchors end."""
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    regex = re.escape(body).replace(r"\*", ".*")
    return re.compile("^" + regex + ("$" if anchored else ""))


def match_path(url: str) -> str:
    """The part of a URL that robots.txt patterns are matched against.

    Path *and* query: a rule like ``Disallow: /*?`` exists to block query
    strings, so comparing it against the path alone can never match.
    """
    parts = urlsplit(url)
    return (parts.path or "/") + (f"?{parts.query}" if parts.query else "")


def is_allowed(parsed: dict, path: str, user_agent: str = "*") -> bool:
    """Allow/Disallow decision (Google precedence: longest matching pattern wins;
    Allow wins ties). Handles ``*`` wildcards and the ``$`` end-anchor.

    ``path`` is the value ``match_path`` returns, query string included."""
    rules = _rules_for(parsed, user_agent)
    best_len, decision = -1, True
    for kind in ("disallow", "allow"):
        allow = kind == "allow"
        for pattern in rules.get(kind, []):
            if pattern == "":
                continue
            if _pattern_to_regex(pattern).match(path):
                plen = len(pattern.rstrip("$"))
                if plen > best_len or (plen == best_len and allow):
                    best_len = plen
                    decision = allow
    return decision


def check_robots(
    url: str, user_agent: str = "*", paths: list[str] | None = None, timeout: float = 20.0
) -> dict:
    robots_url = _robots_url(url)
    try:
        client, _http2_capable = http_client(
            timeout, follow_redirects=True, headers={"User-Agent": _UA}
        )
        with client:
            resp = client.get(robots_url)
    except Exception as exc:
        return {"ok": False, "robots_url": robots_url, "error": str(exc)}
    if resp.status_code >= 400:
        return {
            "ok": True,
            "robots_url": robots_url,
            "status_code": resp.status_code,
            "exists": False,
            "groups": [],
            "sitemaps": [],
            "note": "no robots.txt (crawl allowed)",
        }
    parsed = parse_robots(resp.text)
    result = {
        "ok": True,
        "robots_url": robots_url,
        "status_code": resp.status_code,
        "exists": True,
        "groups": parsed["groups"],
        "sitemaps": parsed["sitemaps"],
    }
    if paths:
        result["path_checks"] = [
            {"path": p, "allowed": is_allowed(parsed, p, user_agent)} for p in paths
        ]
    return result


if __name__ == "__main__":
    sample = "User-agent: *\nDisallow: /api/\nDisallow: /*?\nAllow: /api/public\n\nSitemap: https://x/sitemap.xml"
    parsed = parse_robots(sample)
    assert parsed["sitemaps"] == ["https://x/sitemap.xml"]
    assert is_allowed(parsed, "/api/public/x") is True  # Allow /api/public beats Disallow /api/
    assert is_allowed(parsed, "/api/private") is False
    assert is_allowed(parsed, "/blog") is True
    assert is_allowed(parsed, "/blog?page=2") is False  # matches wildcard Disallow: /*?
    print("OK: robots self-check passed")
