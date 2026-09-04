"""Typed return shapes for the most-reused dict contracts in the toolkit.

Every dict below already exists at runtime: `seohead.tools.parser.parse_url`
and `seohead.tools.robots.check_robots` have returned exactly these keys since
before this module existed. Adding a `TypedDict` for them is purely additive —
it gives a type checker (and a reader) something to verify a caller against,
without changing what either function returns or asking any caller to change.

`TypedDict` was chosen over a dataclass or a Pydantic model for this first
slice because both call sites are already deep in the codebase (crawl,
recon, the CLI/MCP handler layer) passing plain dicts around; a `TypedDict`
describes that same dict, at zero runtime cost, with no migration required.
A Pydantic model remains the right choice where runtime validation at a
boundary is wanted (see issue #31) — that trade-off should stay a deliberate
per-shape decision, not a blanket rule.

Two shapes are covered here, in order of reuse:

- ``ParseResult`` (via ``ParseFetched`` / ``ParseFailed``): the return of
  ``parser.parse_url`` / ``parser.parse_html``, reused by
  ``seohead.tools.page_facts``, ``seohead.tools.links``,
  ``seohead.crawl.collect``, ``seohead.recon.backlinks``,
  ``seohead.recon.regions``, and the ``parse`` / ``citability_check`` /
  ``social_meta_check`` handlers — the single most-shared shape in the package.
- ``RobotsCheckResult`` (via ``RobotsCheckFound`` / ``RobotsCheckError``): the
  return of ``robots.check_robots``, the ``robots_check`` handler's shape and
  a representative "ok/error envelope with a couple of optional keys"
  pattern that recurs across most of the other 42 handlers.
"""

from __future__ import annotations

import sys
from typing import Any, Literal

if sys.version_info >= (3, 12):
    from typing import TypedDict
else:  # pragma: no cover - exercised by the 3.10/3.11 CI jobs
    # Pydantic refuses typing.TypedDict below 3.12: on those versions the
    # runtime cannot see which keys are required, so a shape used in an MCP
    # tool signature would be validated against nothing. typing_extensions
    # backports the __required_keys__ machinery pydantic needs.
    from typing_extensions import TypedDict


class LinkInfo(TypedDict):
    """One `<a href>` extracted from a page."""

    href: str
    text: str
    rel: str
    nofollow: bool
    external: bool


class _ParsedPageOptional(TypedDict, total=False):
    # Only present when the caller opts in via options["url_sources"]=True
    # (off by default) — see parser.parse_html.
    url_sources: list[dict[str, str]]


class ParsedPage(_ParsedPageOptional):
    """The on-page fields `parser.parse_html` extracts (pure, no network)."""

    title: str | None
    meta_description: str | None
    robots: str | None
    robots_meta: list[str]
    canonical: str | None
    og: dict[str, str]
    twitter: dict[str, str]
    headings: dict[str, list[str]]
    jsonld: list[Any]
    jsonld_invalid: list[dict[str, Any]]
    links: list[LinkInfo]
    text: str
    # The whole body, and the content area alone. word_count follows the
    # content area, because a nav-and-footer word count describes the template
    # rather than the page.
    content_text: str
    content_area_strategy: str
    word_count: int


class ParseFetched(ParsedPage):
    """`parser.parse_url` once the request itself completed: page fields plus
    fetch metadata. ``ok`` mirrors the HTTP response (``response.is_success``)
    and can be ``False`` here too — e.g. a clean 404 still parses the body."""

    url: str
    final_url: str
    status_code: int
    ok: bool


class ParseFailed(TypedDict):
    """`parser.parse_url` when the request itself raised (network, timeout,
    invalid URL, ...) before any response existed to parse."""

    url: str
    ok: Literal[False]
    error: str


# parser.parse_url's actual return type: one or the other, never a mix.
ParseResult = ParseFetched | ParseFailed


class ParseManyResult(TypedDict):
    """The `parse` handler's return: one `ParseResult` per requested URL."""

    count: int
    results: list[ParseResult]


class RobotsGroup(TypedDict):
    """One `User-agent:` group from a parsed robots.txt."""

    user_agents: list[str]
    allow: list[str]
    disallow: list[str]
    crawl_delay: float | None


class ParsedRobots(TypedDict):
    """`robots.parse_robots`'s pure parse of robots.txt content."""

    groups: list[RobotsGroup]
    sitemaps: list[str]


class RobotsPathCheck(TypedDict):
    path: str
    allowed: bool


class _RobotsCheckFoundOptional(TypedDict, total=False):
    # Present only on the "no robots.txt" branch (status >= 400).
    note: str
    # Present only when the caller passed `paths`.
    path_checks: list[RobotsPathCheck]


class RobotsCheckFound(_RobotsCheckFoundOptional):
    """`robots.check_robots` once the robots.txt request itself succeeded
    (whether or not a robots.txt actually exists — see `exists`)."""

    ok: Literal[True]
    robots_url: str
    status_code: int
    exists: bool
    groups: list[RobotsGroup]
    sitemaps: list[str]


class RobotsCheckError(TypedDict):
    """`robots.check_robots` when fetching robots.txt itself failed."""

    ok: Literal[False]
    robots_url: str
    error: str


# robots.check_robots's actual return type: one or the other, never a mix.
RobotsCheckResult = RobotsCheckFound | RobotsCheckError
