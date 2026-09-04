"""Resolve a configurable content area for word counts, duplicate and language checks.

Word count, thin-content detection, and duplicate comparison have historically
run over the whole document, so a 40-word product page with a 600-word
mega-menu reads as substantial, and every page on a site looks similar to
every other because they share the same navigation and footer. This module
scopes text extraction to a defined content area instead.

It deliberately touches nothing about link discovery: restricting the content
area is a statement about text, not about which links exist on the page.
Callers that need both must run link extraction over the untouched document
and pass only the resolved root here.

Configuration (all keys optional, passed as one dict):
  include_selector  -- CSS selector naming the main region directly (positive
      selection). Wins over ``root_selector`` when it matches an element.
  root_selector     -- CSS selector for the region to scope exclusions within.
      Defaults to the document ``<body>``.
  exclude_tags      -- tag names removed from the resolved root before text is
      read. Defaults to ``DEFAULT_EXCLUDE_TAGS`` (nav, footer); pass ``[]`` to
      keep everything.
  exclude_selectors -- CSS selectors (by class, id, or anything else) removed
      the same way, for boilerplate that is neither a ``<nav>`` nor a
      ``<footer>``.

This module is pure and performs no network access.
"""

from __future__ import annotations

from copy import copy
from typing import Any

from bs4 import BeautifulSoup, Tag

# Menus and footers are boilerplate, not content, on most sites. Sites that
# name their menu or footer differently use exclude_selectors instead.
DEFAULT_EXCLUDE_TAGS = ("nav", "footer")


def _strip(root: Tag, exclude_tags: Any, exclude_selectors: Any) -> None:
    """Remove excluded elements from ``root`` in place."""
    for tag_name in exclude_tags or ():
        for el in root.find_all(tag_name):
            el.decompose()
    for selector in exclude_selectors or ():
        for el in root.select(selector):
            el.decompose()


def find_content_root(soup: BeautifulSoup, config: dict[str, Any] | None = None) -> tuple[Tag, str]:
    """Return ``(root, strategy)`` for the configured content area, on the live tree.

    This is the selection half of :func:`resolve_content_area`, split out so a
    caller that needs to test descendant membership (link position
    classification: "is this link inside the content area?") can do so by
    identity against the actual document, rather than against the detached,
    stripped copy that word-count and duplicate-detection extraction need.
    Nothing here mutates ``soup``.

    ``strategy`` records how the region was picked so a wrong or missing
    selector is visible per page rather than silently falling back:
      "include_selector"      -- include_selector was given and matched.
      "root_selector"         -- root_selector was given (no include_selector
                                  or it did not match) and matched.
      "default_body"          -- neither selector was configured.
      "fallback_default_body" -- a selector was configured but matched
                                  nothing, so the whole body was used instead.
    """
    config = config or {}
    include_selector = config.get("include_selector")
    root_selector = config.get("root_selector")

    requested_but_missing = False

    if include_selector:
        match = soup.select_one(include_selector)
        if match is not None:
            return match, "include_selector"
        requested_but_missing = True

    if root_selector:
        match = soup.select_one(root_selector)
        if match is not None:
            return match, "root_selector"
        requested_but_missing = True

    strategy = "fallback_default_body" if requested_but_missing else "default_body"
    return soup.body or soup, strategy


def resolve_content_area(
    soup: BeautifulSoup, config: dict[str, Any] | None = None
) -> tuple[Tag, str]:
    """Return ``(content_root, strategy)`` for the configured content area.

    ``content_root`` is a detached copy: it can be decomposed freely without
    disturbing the tree used for link discovery, which never passes through
    this function.
    """
    config = config or {}
    exclude_tags = config.get("exclude_tags", DEFAULT_EXCLUDE_TAGS)
    exclude_selectors = config.get("exclude_selectors")

    live_root, strategy = find_content_root(soup, config)
    root = copy(live_root)
    _strip(root, exclude_tags, exclude_selectors)
    return root, strategy


def extract_area_text(root: Tag) -> str:
    """Collapsed visible text of an already-resolved content root."""
    root = copy(root)
    for tag in root.find_all(["script", "style", "noscript", "template"]):
        tag.decompose()
    return " ".join(root.get_text(" ").split())
