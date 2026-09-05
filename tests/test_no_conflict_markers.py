"""No tracked file carries an unresolved merge-conflict marker.

Markers reached `main` and sat at the top of README.md — the first thing a
visitor sees on GitHub — through a merge whose two sides were *identical*, so
the resolution looked like a no-op and the eye slid past it. Nothing caught it:
`ruff` never reads Markdown, the doc-count gates parse the numbers on a line
without asking what else is on it, and CI's Cyrillic gate looks for a different
thing entirely.

Cheap, total, and derived from the repository rather than from a list of places
worth checking -- the same reasoning as tests/test_interface_binding.py, and for
the same reason: a guard whose scope is typed by hand stops covering what it
claims to.
"""

from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Written split so this file does not match its own assertion.
MARKERS = ("<" * 7 + " ", "=" * 7 + "\n", ">" * 7 + " ")


def _tracked_text_files() -> list[pathlib.Path]:
    """Every tracked file, from git rather than a glob.

    A glob would need a list of extensions, and the next file type added would
    not be covered. Binary files are skipped by the read itself.
    """
    listed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return [ROOT / name for name in listed.split("\0") if name]


def test_no_tracked_file_has_an_unresolved_conflict_marker():
    offenders: list[str] = []
    for path in _tracked_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary, or a path git lists that no longer exists
        for number, line in enumerate(text.splitlines(keepends=True), start=1):
            if any(line.startswith(marker) for marker in MARKERS):
                offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.rstrip()}")
    assert not offenders, "unresolved merge-conflict markers:\n" + "\n".join(offenders)
