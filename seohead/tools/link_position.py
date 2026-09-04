"""Classify a link by where it sits in the page: nav, header, sidebar, footer, or content.

A link's ancestor chain says more about it than its href does: a broken link
repeated in a global footer is one template fix, and a page linked only from
that footer is not linked the way a page linked from body copy is. Neither
fact is visible from the URL list alone.

Classification is ordered rules over the link's own ancestor path, tested with
``soupsieve.closest`` (the same matcher BeautifulSoup's ``.select`` uses under
the hood) rather than a hand-rolled ancestor walk. The built-in rules cover
``<nav>``/``<header>``/``<aside>``/``<footer>`` and their common ARIA-role and
class-name equivalents; site-specific rules are expected on top, because
plenty of menus are not a ``<nav>`` element at all. Rules are tried in order
and the first match wins, which is what "site-specific rules run first" means
in practice: a caller can prepend a rule that reclassifies a specific block
before the built-ins ever see it.

The last bucket, "content", is deliberately not one more selector on the same
list. It reuses ``content_area.find_content_root`` -- the same notion of
"where the content is" that word counts and duplicate detection already use --
by identity: a link is "content" when it descends from that resolved root and
matched no boilerplate rule first. This module never invents a second
definition of content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import soupsieve
from bs4 import Tag

# "content" is deliberately absent here: it is resolved structurally (see
# module docstring), never by a selector, so it cannot be shadowed by a
# same-named site-specific rule matching the wrong element.
POSITIONS: tuple[str, ...] = ("nav", "header", "sidebar", "footer", "content", "other")


@dataclass(frozen=True)
class PositionRule:
    """One ordered rule: a CSS selector tested against a link's ancestor path."""

    position: str
    selector: str


# role=... covers sites that skip the matching semantic tag. Class names are a
# concession to real templates: plenty of production menus are a styled <div>.
DEFAULT_RULES: tuple[PositionRule, ...] = (
    PositionRule(
        "nav",
        "nav, [role='navigation'], .nav, .navbar, .menu, .main-menu, .primary-menu, .breadcrumb",
    ),
    PositionRule("header", "header, [role='banner'], .site-header, .page-header"),
    PositionRule("sidebar", "aside, [role='complementary'], .sidebar, .widget-area"),
    PositionRule("footer", "footer, [role='contentinfo'], .site-footer, .page-footer"),
)


def rules_from_config(rules: Any) -> tuple[PositionRule, ...]:
    """Build an ordered rule tuple from plain ``{"position", "selector"}`` dicts.

    ``None`` or an empty sequence keeps :data:`DEFAULT_RULES`. A non-empty
    sequence *replaces* them rather than appending, so a caller who wants the
    built-ins plus one more rule includes ``DEFAULT_RULES`` explicitly -- an
    implicit merge would make the effective rule order (and therefore which
    rule wins) impossible to read from the config alone.
    """
    if not rules:
        return DEFAULT_RULES
    return tuple(PositionRule(str(r["position"]), str(r["selector"])) for r in rules)


def classify_link(
    link_tag: Tag,
    content_root: Tag | None,
    *,
    rules: tuple[PositionRule, ...] | None = None,
) -> str:
    """Classify one already-parsed ``<a>`` tag by its ancestor path.

    ``content_root`` is the *live-tree* element returned by
    ``content_area.find_content_root`` for the same document -- not the
    detached, stripped copy ``resolve_content_area`` returns for text
    extraction, since only the live tree lets identity comparison answer "is
    this link a descendant of the content root".

    Rules are tried in order; the first whose selector matches the link itself
    or any ancestor wins. This is the ordered, catch-all-last shape the rules
    are specified to have: a malformed site-specific selector is skipped
    rather than raised, so one bad rule cannot break classification for the
    rest of the page. When no rule matches, the link is "content" if it
    descends from ``content_root`` and "other" otherwise -- "other" only
    arises when a narrower ``include_selector``/``root_selector`` was
    configured and a link sits entirely outside it (e.g. a global element that
    is neither content nor recognized boilerplate); with the default
    whole-``<body>`` content root every link is "content" by elimination.
    """
    for rule in rules or DEFAULT_RULES:
        try:
            if soupsieve.closest(rule.selector, link_tag) is not None:
                return rule.position
        except Exception:
            continue  # an invalid site-specific selector must not break the crawl
    if content_root is not None:
        for ancestor in (link_tag, *link_tag.parents):
            if ancestor is content_root:
                return "content"
        return "other"
    return "content"
