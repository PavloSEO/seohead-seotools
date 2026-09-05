"""Offline tests for Markdown extraction (issue #19, part 2)."""

from seohead.tools import markdown_extract as M

_HTML = """<html><body>
<nav>Home About Contact</nav>
<main id="content">
<h1>Widget Pro</h1>
<p>A <strong>durable</strong> widget for <em>everyone</em>.</p>
<ul><li>Feature one</li><li>Feature two</li></ul>
<p>See the <a href="/specs">specs</a> for details.</p>
</main>
<footer>Copyright 2026 Acme</footer>
</body></html>"""


def test_content_markdown_strips_boilerplate_but_keeps_structure():
    out = M.extract_markdown(_HTML, {"include_selector": "#content"})
    md = out["content_markdown"]
    assert "# Widget Pro" in md
    assert "**durable**" in md
    assert "*everyone*" in md
    assert "- Feature one" in md and "- Feature two" in md
    assert "[specs](/specs)" in md
    assert "Home About Contact" not in md
    assert "Copyright" not in md
    assert out["content_area_strategy"] == "include_selector"


def test_full_markdown_includes_header_and_footer():
    out = M.extract_markdown(_HTML, {"include_selector": "#content"})
    assert "Home About Contact" in out["full_markdown"]
    assert "Copyright 2026 Acme" in out["full_markdown"]
    assert "# Widget Pro" in out["full_markdown"]


def test_default_content_area_used_when_no_config_given():
    out = M.extract_markdown(_HTML)
    # No configuration: the region comes from the document's own semantics (#96).
    assert out["content_area_strategy"] == "auto_main"
    assert "Home About Contact" not in out["content_markdown"]
    assert "Copyright" not in out["content_markdown"]


def test_semantic_wrapper_does_not_flatten_headings_and_lists():
    """A direct <article>/<section>/<div> child used to be handed to _inline(),
    which has no notion of headings or lists and just concatenates every
    descendant's text -- discarding every "#"/"-" marker nested inside it
    (issue #230)."""
    html = (
        "<main><article><h1>Widget guide</h1><p>Intro text.</p>"
        "<ul><li>First step</li><li>Second step</li></ul></article></main>"
    )
    out = M.extract_markdown(html)
    md = out["content_markdown"]
    assert "# Widget guide" in md
    assert "Intro text." in md
    assert "- First step" in md
    assert "- Second step" in md
    # The pre-fix bug ran every descendant's text together with no separator.
    assert "Widget guideIntro text." not in md
    assert "First stepSecond step" not in md


def test_nested_wrapper_two_levels_deep_still_preserves_structure():
    """A <section> wrapping an <article> wrapping the real content: the fix must
    recurse through every layout layer, not just the outermost one."""
    html = "<section><article><h2>Deep heading</h2><ul><li>Only item</li></ul></article></section>"
    out = M.extract_markdown(html)
    md = out["full_markdown"]
    assert "## Deep heading" in md
    assert "- Only item" in md
