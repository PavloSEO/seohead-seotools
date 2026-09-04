"""Every issue this toolkit can find must appear in at least one scenario.

The scenario catalogue is the interface for anybody — person or agent — deciding what this
repository can do end to end. A capability that exists in the registry and appears in no
scenario is a capability nobody will find, which makes it, in practice, absent.

So the coverage map decides which scenarios exist, rather than somebody's idea of a good list:
each scenario declares the catalogued issues it resolves in a "Covers" section, and this test
asserts the union is everything we claim to find.
"""

from __future__ import annotations

import pathlib
import re

from seohead.sf.core.sf_issue_map import CATEGORIES

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCENARIOS = sorted(p for p in (ROOT / "docs" / "scenarios").glob("*.md") if p.name != "README.md")

# "Covers" lines look like:  - **Category** — Issue One · Issue Two
_COVERS_BLOCK = re.compile(r"^## Covers\b(.*?)(?=^## |\Z)", re.M | re.S)
_COVERS_ROW = re.compile(r"^-\s+\*\*(?P<category>[^*]+)\*\*\s+—\s+(?P<items>.+)$", re.M)


def _declared() -> dict[str, set[str]]:
    """Category -> issue names, as declared across every scenario."""
    out: dict[str, set[str]] = {}
    for path in SCENARIOS:
        block = _COVERS_BLOCK.search(path.read_text(encoding="utf-8"))
        if not block:
            continue
        for row in _COVERS_ROW.finditer(block.group(1)):
            category = row.group("category").strip()
            items = [i.strip() for i in row.group("items").split("·") if i.strip()]
            out.setdefault(category, set()).update(items)
    return out


def _findable() -> dict[str, set[str]]:
    """Category -> issue names we claim to find, from the coverage map."""
    return {
        category: {e.name for e in items if e.status in ("check", "tool", "partial")}
        for category, items in CATEGORIES.items()
        if any(e.status in ("check", "tool", "partial") for e in items)
    }


def test_every_scenario_declares_what_it_covers():
    missing = [p.name for p in SCENARIOS if not _COVERS_BLOCK.search(p.read_text(encoding="utf-8"))]
    assert not missing, f"scenarios with no '## Covers' section: {missing}"


def test_every_declared_issue_exists_in_the_coverage_map():
    findable = _findable()
    unknown = []
    for category, items in _declared().items():
        known = findable.get(category, set())
        for item in items:
            if item not in known:
                unknown.append(f"{category}/{item}")
    assert not unknown, (
        f"scenarios name issues the coverage map does not list as findable: {unknown}"
    )


def test_every_findable_issue_appears_in_a_scenario():
    declared = _declared()
    uncovered = []
    for category, items in _findable().items():
        shown = declared.get(category, set())
        for item in sorted(items - shown):
            uncovered.append(f"{category}/{item}")
    assert not uncovered, (
        f"{len(uncovered)} issues this toolkit finds appear in no scenario: {uncovered}"
    )


def test_every_scenario_says_what_it_cannot_answer():
    """A scenario without its limits is marketing, and an agent that trusts it reports a
    confident wrong answer."""
    missing = [
        p.name for p in SCENARIOS if "cannot answer" not in p.read_text(encoding="utf-8").lower()
    ]
    assert not missing, f"scenarios with no limits section: {missing}"
