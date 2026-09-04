"""Render the check catalogue documentation from ``CHECKS``, the registry itself.

The registry is already the single source of truth for severity, evidence, message
and fix (see its module docstring). Restating any of that by hand in a Markdown file
would just be a second copy that can silently disagree with the first, which is the
exact failure this module exists to remove: ``docs/CHECKS.md`` is generated, and
``tests/test_docs_drift.py`` fails the build the moment it stops matching.
"""

from __future__ import annotations

import re
from pathlib import Path

from seohead.sf.core.registry import CHECKS

REGISTRY_SOURCE = Path(__file__).with_name("registry.py")

_SECTION_RE = re.compile(r"^    # (.+)$")
_CHECK_ID_RE = re.compile(r'^    "([A-Z0-9_]+)": \{$')


def _sections() -> dict[str, str]:
    """Map each check id to the nearest ``# ...`` banner above it in registry.py.

    The banners split the flat ``CHECKS`` dict into the groups a human already
    reads it in (7.A indexing, 7.B links, the extension blocks, ...). Parsing the
    source rather than hand-listing the groups here means a renamed or reordered
    section can never drift from what the reference actually shows.
    """
    text = REGISTRY_SOURCE.read_text(encoding="utf-8")
    body = text.split("CHECKS: dict[str, dict[str, Any]] = {", 1)[1]
    body = body.split("\ndef check_meta", 1)[0]

    section_of: dict[str, str] = {}
    current = "Uncategorized"
    for line in body.splitlines():
        section_match = _SECTION_RE.match(line)
        if section_match:
            current = section_match.group(1)
            continue
        check_match = _CHECK_ID_RE.match(line)
        if check_match:
            section_of[check_match.group(1)] = current
    return section_of


def render() -> str:
    """Build the full CHECKS.md content from the live registry."""
    section_of = _sections()
    lines = [
        "# Check catalogue",
        "",
        "Generated from `seohead/sf/core/registry.py` — do not edit by hand. Regenerate with:",
        "",
        "```bash",
        "python scripts/generate_checks_reference.py",
        "```",
        "",
        f"**{len(CHECKS)} checks.** Severity, evidence and fix all come from the same "
        "`CHECKS` dict the rule engine reads, so this table cannot say something the "
        "engine disagrees with.",
        "",
        "- **Fires on** — what the check id means, in the registry's own words.",
        "- **Evidence** — the `source` tag: which export or module has to be present for "
        "the check to run at all; its absence is why a check comes back `skipped` instead "
        "of a silent pass.",
        "- **Fix** — the remedy the audit ships next to the finding.",
        "",
    ]

    seen_sections: list[str] = []
    by_section: dict[str, list[str]] = {}
    for check_id in CHECKS:
        section = section_of.get(check_id, "Uncategorized")
        if section not in by_section:
            seen_sections.append(section)
            by_section[section] = []
        by_section[section].append(check_id)

    for section in seen_sections:
        lines.append(f"## {section}")
        lines.append("")
        lines.append("| Check id | Severity | Evidence | Fires on | Fix |")
        lines.append("|---|---|---|---|---|")
        for check_id in by_section[section]:
            meta = CHECKS[check_id]
            lines.append(
                f"| `{check_id}` | {meta['severity']} | {meta['source']} "
                f"| {meta['message']} | {meta['fix']} |"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
