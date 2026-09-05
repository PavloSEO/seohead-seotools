"""Render a page as Markdown, in two scopes: content-area only and full document.

A word count or a hash tells you *that* a page changed; neither is worth
diffing between crawls, feeding to content scoring, or handing to a model
directly. Markdown with structure preserved (headings, lists, links) is.

Two renderings answer different questions:
  - ``content_markdown`` -- boilerplate stripped, via ``content_area.py``.
    This is the representation worth diffing, scoring, or feeding to a model.
  - ``full_markdown`` -- the whole document, header and footer included. Not a
    debug artefact: it is the input to ``boilerplate_report.py``'s hashing.

The converter below is intentionally small and handles only the tags visible
body text realistically uses (headings, paragraphs, lists, links, emphasis).
It is our own code rather than a third-party extractor on purpose: a
third-party converter's output is version-dependent, which would either pull
Markdown text outside the determinism gate or require pinning and recording a
version. A deterministic, dependency-free renderer avoids the trade-off.

This module is pure and performs no network access.
"""

from __future__ import annotations

from bs4 import BeautifulSoup, NavigableString, Tag

from seohead.tools.content_area import resolve_content_area

_BLOCK_TAGS = {"p", "div", "section", "article", "li", "blockquote"}
_HEADING_LEVELS = {f"h{i}": i for i in range(1, 7)}
_STRUCTURAL_TAGS = _BLOCK_TAGS | set(_HEADING_LEVELS) | {"ul", "ol"}


def _inline(node: Tag | NavigableString) -> str:
    """Render inline content: text, links, and bold/italic emphasis."""
    if isinstance(node, NavigableString):
        return str(node)
    if node.name in ("script", "style", "noscript", "template"):
        return ""
    if node.name == "br":
        return "\n"
    if node.name == "a":
        text = "".join(_inline(c) for c in node.children).strip()
        href = node.get("href")
        return f"[{text}]({href})" if href and text else text
    if node.name in ("strong", "b"):
        text = "".join(_inline(c) for c in node.children).strip()
        return f"**{text}**" if text else ""
    if node.name in ("em", "i"):
        text = "".join(_inline(c) for c in node.children).strip()
        return f"*{text}*" if text else ""
    return "".join(_inline(c) for c in node.children)


def to_markdown(root: Tag) -> str:
    """Render an element tree as Markdown with headings, lists, and links preserved.

    Block elements become their own line(s); list items are bulleted.
    Consecutive blank lines are collapsed so boilerplate removal upstream
    (which decomposes whole elements) doesn't leave gaps.
    """
    lines: list[str] = []

    def walk(node: Tag) -> None:
        for child in node.children:
            if isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    lines.append(text)
                continue
            if child.name in ("script", "style", "noscript", "template"):
                continue
            if child.name in _HEADING_LEVELS:
                text = _inline(child).strip()
                if text:
                    lines.append(f"{'#' * _HEADING_LEVELS[child.name]} {text}")
                continue
            if child.name in ("ul", "ol"):
                for i, li in enumerate(child.find_all("li", recursive=False), start=1):
                    text = _inline(li).strip()
                    if text:
                        marker = f"{i}." if child.name == "ol" else "-"
                        lines.append(f"{marker} {text}")
                continue
            if child.name in _BLOCK_TAGS:
                # A semantic wrapper such as ``article`` commonly contains the
                # headings and lists that this renderer promises to preserve.
                # Rendering it inline would flatten those descendants together.
                if child.find(list(_STRUCTURAL_TAGS)):
                    walk(child)
                    continue
                text = _inline(child).strip()
                if text:
                    lines.append(text)
                else:
                    walk(child)  # a container with only nested blocks, not text
                continue
            walk(child)  # unrecognized wrapper: descend without emitting a line

    walk(root)
    return "\n\n".join(lines)


def extract_markdown(html: str, content_area_config: dict | None = None) -> dict[str, str]:
    """Return ``{"content_markdown", "full_markdown", "content_area_strategy"}`` for ``html``."""
    soup = BeautifulSoup(html, features="lxml")
    full_root = soup.body or soup
    content_root, strategy = resolve_content_area(soup, content_area_config)
    return {
        "content_markdown": to_markdown(content_root),
        "full_markdown": to_markdown(full_root),
        "content_area_strategy": strategy,
    }
