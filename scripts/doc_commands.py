"""Extract every ``seohead ...`` invocation shown in the documentation.

Both ``tests/test_docs_commands_execute.py`` (which runs each one against fixtures
in CI) and anyone auditing the docs by hand import this module, so there is exactly
one place that knows what counts as "a command shown in the documentation" and how
to turn the Markdown text of one back into an argv list.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path

FENCE_RE = re.compile(r"```(?:bash|sh|shell)?\n(.*?)```", re.S)
ECHO_PIPE_RE = re.compile(r"^echo\s+'(?P<payload>.*)'\s*\|\s*seohead\s+(?P<rest>.+)$")


def doc_files(root: Path) -> list[Path]:
    """Every Markdown file whose fenced examples are part of the public contract."""
    return sorted(
        [
            root / "README.md",
            root / "AGENTS.md",
            root / "CONTRIBUTING.md",
            *(root / "docs").glob("*.md"),
            *(root / ".claude" / "skills").glob("*/SKILL.md"),
            *(root / "seohead" / "skills").glob("*/SKILL.md"),
            *(root / "examples").glob("**/README.md"),
        ]
    )


@dataclass(frozen=True)
class DocCommand:
    source: Path
    raw: str  # the command text as shown in the docs, comments/continuations resolved
    stdin: str | None  # payload to pipe in, for the `echo '...' | seohead ...` form


def _join_continuations(block: str) -> list[str]:
    """Merge a fenced block's lines into logical commands.

    Two Markdown conventions both split one command across lines: an explicit
    trailing ``\\`` (shell continuation), and a quoted JSON literal that simply
    wraps without one (readable in the doc, still one shell token once quoted).
    Both are done accumulating once the buffer has no trailing backslash and its
    quotes balance.
    """
    logical: list[str] = []
    buf = ""
    for line in block.splitlines():
        buf = f"{buf}\n{line}" if buf else line
        if buf.rstrip().endswith("\\"):
            buf = buf.rstrip()[:-1]
            continue
        if buf.count("'") % 2 or buf.count('"') % 2:
            continue  # quotes still open; fold in the next line
        logical.append(buf)
        buf = ""
    if buf:
        logical.append(buf)
    return logical


def _strip_comment(line: str) -> str:
    """Drop a trailing ``# ...`` annotation, respecting quotes via shlex."""
    try:
        tokens = shlex.split(line, comments=True)
    except ValueError:
        return line.split(" #", 1)[0].rstrip()
    return shlex.join(tokens)


def extract_commands(root: Path) -> list[DocCommand]:
    """Every documented ``seohead`` invocation, one entry per logical command line."""
    commands: list[DocCommand] = []
    for path in doc_files(root):
        text = path.read_text(encoding="utf-8")
        for block in FENCE_RE.findall(text):
            for line in _join_continuations(block):
                candidate = line.strip()
                if candidate.startswith("$ "):
                    candidate = candidate[2:].strip()
                echo_match = ECHO_PIPE_RE.match(candidate)
                if echo_match:
                    rest = _strip_comment("seohead " + echo_match.group("rest"))
                    commands.append(
                        DocCommand(source=path, raw=rest, stdin=echo_match.group("payload"))
                    )
                    continue
                if not candidate.startswith("seohead "):
                    continue
                stripped = _strip_comment(candidate)
                if stripped:
                    commands.append(DocCommand(source=path, raw=stripped, stdin=None))
    return commands


def to_argv(raw: str) -> list[str]:
    """The command text (``seohead ...``) as an argv list, ``seohead`` itself dropped.

    A trailing ``> file`` shown for readability (redirecting stdout in a shell) is not
    a CLI argument; it is dropped rather than passed through as a bogus positional.
    """
    tokens = shlex.split(raw)[1:]
    if ">" in tokens:
        tokens = tokens[: tokens.index(">")]
    return tokens
