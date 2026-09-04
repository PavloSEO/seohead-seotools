"""Offline tests for the configurable content area (issue #19, part 1)."""

from bs4 import BeautifulSoup

from seohead.tools import content_area
from seohead.tools.parser import parse_html

_HTML = """<html><body>
<nav>Home Products Services About Contact Blog Careers Support Login Sign up now</nav>
<main id="content"><h1>Widget</h1><p>A short but real product description.</p>
<a href="/related">related</a></main>
<footer>Copyright policy terms privacy sitemap careers investors press newsletter</footer>
</body></html>"""


def _soup() -> BeautifulSoup:
    return BeautifulSoup(_HTML, features="lxml")


# ── resolve_content_area ──────────────────────────────────────────────────────


def test_default_excludes_nav_and_footer():
    root, strategy = content_area.resolve_content_area(_soup())
    assert strategy == "default_body"
    text = content_area.extract_area_text(root)
    assert "Widget" in text and "short but real product description" in text
    assert "Sign up now" not in text  # nav
    assert "newsletter" not in text  # footer


def test_include_selector_wins_and_is_recorded():
    root, strategy = content_area.resolve_content_area(_soup(), {"include_selector": "#content"})
    assert strategy == "include_selector"
    text = content_area.extract_area_text(root)
    assert "Widget" in text
    assert "Sign up now" not in text


def test_missing_selector_falls_back_and_says_so():
    root, strategy = content_area.resolve_content_area(_soup(), {"include_selector": "#nope"})
    assert strategy == "fallback_default_body"
    # Still falls back to the whole (exclusion-filtered) body, not an empty region.
    assert "Widget" in content_area.extract_area_text(root)


def test_exclude_selectors_removes_class_or_id_based_boilerplate():
    html = (
        '<html><body><div class="mega-menu">Deals Sale Clearance</div>'
        "<p>Real content here.</p></body></html>"
    )
    soup = BeautifulSoup(html, features="lxml")
    root, strategy = content_area.resolve_content_area(soup, {"exclude_selectors": [".mega-menu"]})
    assert strategy == "default_body"
    text = content_area.extract_area_text(root)
    assert "Real content here." in text
    assert "Deals" not in text


def test_exclude_tags_empty_list_disables_the_default_exclusions():
    root, _strategy = content_area.resolve_content_area(_soup(), {"exclude_tags": []})
    text = content_area.extract_area_text(root)
    assert "Sign up now" in text  # nav kept this time
    assert "newsletter" in text  # footer kept this time


# ── parser.parse_html integration: acceptance criteria 1 and 2 ───────────────


def test_word_count_changes_with_content_area_but_link_count_does_not():
    # A content area covering the whole body (exclusions disabled) versus one
    # scoped to the article: the same page, two different regions.
    full = parse_html(_HTML, "https://example.com/page", {"content_area": {"exclude_tags": []}})
    scoped = parse_html(
        _HTML, "https://example.com/page", {"content_area": {"include_selector": "#content"}}
    )
    assert scoped["word_count"] < full["word_count"]
    # Restricting the content area is a statement about text, not about links.
    assert len(scoped["links"]) == len(full["links"])
    assert any(link["href"].endswith("/related") for link in full["links"])


def test_content_area_strategy_appears_per_page():
    default = parse_html(_HTML, "https://example.com/page")
    assert default["content_area_strategy"] == "default_body"
    scoped = parse_html(
        _HTML, "https://example.com/page", {"content_area": {"root_selector": "#nope"}}
    )
    assert scoped["content_area_strategy"] == "fallback_default_body"


def test_content_area_strategy_none_when_text_disabled():
    off = parse_html(_HTML, "https://example.com/page", {"text": False})
    assert off["content_area_strategy"] is None
    assert off["word_count"] == 0
