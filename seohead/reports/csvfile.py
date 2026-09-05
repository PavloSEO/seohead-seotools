"""Write flat CSV records for a task tracker or downstream database.

One file represents one entity, so the renderer writes two adjacent files:
``<name>.csv`` contains findings and ``<name>.pages.csv`` contains pages. Mixing
different entities into a single table produces an ambiguous file that is difficult
or impossible to import reliably.

Named ``csvfile`` rather than ``csv``: a module named ``csv.py`` next to code that does
``import csv`` for the standard library would shadow it. This is deliberate, not an
inconsistency to align with the other format modules in this package (see docs/NAMING.md).
"""

from __future__ import annotations

import csv
import pathlib
from typing import Any


def write(document: dict[str, Any], path: pathlib.Path) -> None:
    from seohead.reports import SEVERITY_TITLES, format_locations, neutralize_formula

    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        # ``utf-8-sig`` includes a BOM so Excel detects UTF-8 instead of corrupting
        # multilingual URLs, titles, and finding evidence when the file is opened.
        writer = csv.writer(fh, delimiter=";")
        # A task tracker importing this file needs the same evidence the
        # documented developer handoff promises (docs/scenarios/broken-pages.md):
        # which check fired, the status code, how many occurrences, every
        # linking location, and the fix hint (#220).
        writer.writerow(
            [
                "Severity",
                "Source",
                "URL",
                "Finding",
                "Check",
                "Status",
                "Occurrences",
                "Locations",
                "Fix Hint",
            ]
        )
        for finding in document.get("findings") or []:
            writer.writerow(
                [
                    SEVERITY_TITLES.get(finding.get("severity"), finding.get("severity")),
                    neutralize_formula(finding.get("source", "")),
                    neutralize_formula(finding.get("url", "")),
                    neutralize_formula(finding.get("text", "")),
                    finding.get("check", ""),
                    finding.get("status_code", ""),
                    finding.get("occurrences_count", ""),
                    neutralize_formula(format_locations(finding.get("locations"))),
                    neutralize_formula(finding.get("fix_hint", "")),
                ]
            )

    pages = document.get("pages") or []
    if pages:
        columns = [
            "url",
            "status",
            "title",
            "title_length",
            "description_length",
            "h1",
            "canonical",
            "words",
            "schema_types",
            "schema_errors",
            "social_missing",
        ]
        pages_path = path.with_suffix(".pages.csv")
        with pages_path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh, delimiter=";")
            writer.writerow(columns)
            for page in pages:
                writer.writerow([neutralize_formula(page.get(c, "")) for c in columns])
