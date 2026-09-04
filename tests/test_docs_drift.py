"""Public documentation must become noisy when product registries drift."""

from __future__ import annotations

import ast
import pathlib
import re
import tokenize

from seohead.cli import COMMANDS, URL_COMMANDS
from seohead.servers.handlers import HANDLERS
from seohead.sf.core.checks_reference import render as render_checks_reference
from seohead.sf.core.registry import CHECKS

ROOT = pathlib.Path(__file__).resolve().parent.parent
TECHNICAL_SKILLS = sorted((ROOT / ".claude" / "skills").glob("*/SKILL.md"))
PACKAGED_SKILLS = sorted((ROOT / "seohead" / "skills").glob("*/SKILL.md"))
DOCS = sorted((ROOT / "docs").glob("*.md"))
PUBLIC_MARKDOWN = [
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "CHANGELOG.md",
    ROOT / "CODE_OF_CONDUCT.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "PROVENANCE.md",
    ROOT / "SECURITY.md",
    ROOT / "THIRD_PARTY_NOTICES.md",
    ROOT / "TRADEMARKS.md",
    *TECHNICAL_SKILLS,
    *PACKAGED_SKILLS,
    *DOCS,
]
PUBLIC_PYTHON = sorted((ROOT / "seohead").glob("**/*.py")) + sorted(
    (ROOT / "tests").glob("**/*.py")
)

EXTRA_COMMANDS = {"sf", "mcp"}
# This literal Cyrillic range intentionally detects non-English public prose.
CYRILLIC = re.compile(r"[А-Яа-яЁё]")  # noqa: RUF001
ALLOWED_LOCALIZED_MARKDOWN = {
    ROOT / "seohead" / "skills" / "article-writer" / "SKILL.md": (
        "N минут чтения",
        "5 минут чтения",
    ),
}


def _sf_tool_names() -> set[str]:
    source = (ROOT / "seohead" / "servers" / "sf_mcp.py").read_text(encoding="utf-8")
    return set(re.findall(r"def (sf_[a-z0-9_]+)\(", source))


def test_every_command_has_a_handler():
    missing = sorted(command for command in COMMANDS if command.replace("-", "_") not in HANDLERS)
    assert not missing, f"CLI commands without handlers: {missing}"


def test_every_handler_is_reachable_from_the_cli():
    exposed = {command.replace("-", "_") for command in COMMANDS}
    orphaned = sorted(set(HANDLERS) - exposed)
    assert not orphaned, f"handlers unavailable through the CLI: {orphaned}"


def test_url_commands_are_registered_commands():
    unknown = sorted(set(URL_COMMANDS) - set(COMMANDS))
    assert not unknown, f"unknown entries in URL_COMMANDS: {unknown}"


def test_skill_name_matches_its_folder():
    bad = []
    for path in [*TECHNICAL_SKILLS, *PACKAGED_SKILLS]:
        match = re.search(r"^name:\s*(\S+)", path.read_text(encoding="utf-8"), re.M)
        if not match or match.group(1) != path.parent.name:
            bad.append(str(path.relative_to(ROOT)))
    assert not bad, f"skill name/folder mismatches: {bad}"


def test_every_skill_has_a_description():
    bad = [
        str(path.relative_to(ROOT))
        for path in [*TECHNICAL_SKILLS, *PACKAGED_SKILLS]
        if not re.search(r"^description:", path.read_text(encoding="utf-8"), re.M)
    ]
    assert not bad, f"skills without a discoverable description: {bad}"


def test_skills_and_docs_reference_only_existing_commands():
    known = set(COMMANDS) | EXTRA_COMMANDS
    bad: list[str] = []
    for path in PUBLIC_MARKDOWN:
        text = path.read_text(encoding="utf-8")
        for used in sorted(set(re.findall(r"seohead\s+([a-z0-9][a-z0-9-]+)", text))):
            if used not in known:
                bad.append(f"{path.relative_to(ROOT)}: seohead {used}")
    assert not bad, "references to non-existent commands: " + "; ".join(bad)


def test_documented_product_counts_match_the_registries():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    provenance = (ROOT / "PROVENANCE.md").read_text(encoding="utf-8")
    assert len(COMMANDS) == len(HANDLERS) == 47
    assert len(_sf_tool_names()) == 5
    assert len(CHECKS) == 104
    assert len(TECHNICAL_SKILLS) == 21
    assert len(PACKAGED_SKILLS) == 7
    for text in (readme, provenance):
        assert "47" in text and "104" in text and "five" in text.lower()
    assert "52 callable tools" in readme
    assert "28 workflow skills" in readme
    assert (ROOT / "CITATION.cff").is_file()


def test_public_markdown_is_english():
    bad = []
    for path in PUBLIC_MARKDOWN:
        text = path.read_text(encoding="utf-8")
        for allowed in ALLOWED_LOCALIZED_MARKDOWN.get(path, ()):
            text = text.replace(allowed, "")
        if CYRILLIC.search(text):
            bad.append(str(path.relative_to(ROOT)))
    assert not bad, f"Cyrillic prose remains in public Markdown: {bad}"


def test_python_comments_and_docstrings_are_english():
    """Allow localized test/data values while keeping explanatory prose English."""
    bad: list[str] = []
    for path in PUBLIC_PYTHON:
        with path.open("rb") as handle:
            for token in tokenize.tokenize(handle.readline):
                if token.type == tokenize.COMMENT and CYRILLIC.search(token.string):
                    bad.append(f"{path.relative_to(ROOT)}:{token.start[0]} comment")

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                docstring = ast.get_docstring(node, clean=False)
                if docstring and CYRILLIC.search(docstring):
                    bad.append(f"{path.relative_to(ROOT)}:{getattr(node, 'lineno', 1)} docstring")

    assert not bad, "Cyrillic remains in comments/docstrings: " + "; ".join(bad)


def test_checks_reference_is_generated_and_current():
    """docs/CHECKS.md is generated output (scripts/generate_checks_reference.py); a hand
    edit or a registry change without regenerating it must fail here rather than ship as
    stale prose. This is the check catalogue the issue calls out as having no coverage."""
    committed = (ROOT / "docs" / "CHECKS.md").read_text(encoding="utf-8")
    assert committed == render_checks_reference(), (
        "docs/CHECKS.md is stale: run scripts/generate_checks_reference.py and commit the result"
    )
    documented = set(re.findall(r"^\| `([A-Z0-9_]+)`", committed, re.M))
    assert documented == set(CHECKS), "every check must appear in the generated reference"


def test_every_cli_command_is_documented_in_tools_reference():
    tools_doc = (ROOT / "docs" / "TOOLS.md").read_text(encoding="utf-8")
    missing = sorted(command for command in COMMANDS if f"`{command}`" not in tools_doc)
    assert not missing, f"commands missing from docs/TOOLS.md: {missing}"


def test_severity_breakdown_in_tools_reference_matches_the_registry():
    from collections import Counter

    counts = Counter(meta["severity"] for meta in CHECKS.values())
    tools_doc = (ROOT / "docs" / "TOOLS.md").read_text(encoding="utf-8")
    expected = (
        f"{counts['critical']} critical, {counts['warning']} warnings, {counts['notice']} notices"
    )
    assert expected in tools_doc, f"docs/TOOLS.md severity breakdown is stale, expected: {expected}"


def test_private_research_journal_is_not_part_of_the_snapshot():
    assert not (ROOT / "maybe").exists()
    combined = "\n".join(path.read_text(encoding="utf-8") for path in PUBLIC_MARKDOWN)
    assert "review of 85" not in combined.lower()
    assert "private development repository is stronger" not in combined.lower()
