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


def test_nested_semantic_wrapper_keeps_markdown_structure():
    html = """<main><article>
    <h1>Widget guide</h1><p>Intro text.</p>
    <ul><li>First step</li><li>Second step</li></ul>
    </article></main>"""

    markdown = M.extract_markdown(html)["content_markdown"]

    assert "# Widget guide" in markdown
    assert "Intro text." in markdown
    assert "- First step" in markdown
    assert "- Second step" in markdown
