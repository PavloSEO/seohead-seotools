"""One append-only journal of every command and MCP call this toolkit runs.

Two problems this solves, and the second is the reason it is worth building.

**Answering "what did the agent actually do".** A CLI and a stdio MCP server both
leave nothing behind once the process exits. When an audit produced a surprising
number, the question is which tools ran, against what, with which arguments and
how long they took — and today that is unanswerable after the fact.

**Making repeated work visible before it is repeated.** Every entry carries a
fingerprint of the call and where its output landed, so a later run can see that
the same tool ran against the same target minutes ago. This module records; it
does not yet skip anything. Reuse is a decision for a caller who knows whether a
stale answer is acceptable, and that is deliberately not decided here.

Format is JSONL, one line per call, appended after the call completes so an
interrupted process cannot corrupt earlier entries. Default path is
``~/.config/seohead/runs.jsonl``; override with ``SEOHEAD_RUN_LOG``, or set
``log.path`` in the config file. Set ``SEOHEAD_RUN_LOG=off`` to disable.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

DEFAULT_PATH = "~/.config/seohead/runs.jsonl"

# Argument names whose values must never reach the journal. Matched as
# substrings, lowercased, because provider clients spell them differently.
SECRET_HINTS = ("token", "key", "secret", "password", "passwd", "auth", "credential")

MAX_VALUE_CHARS = 300

# Which face of the toolkit is running. Set once at process start so a single
# journaling point can name the caller without every call site passing it.
_interface = "library"


def set_interface(name: str) -> None:
    global _interface
    _interface = name


def current_interface() -> str:
    return _interface


def log_path() -> Path | None:
    """Where the journal lives, or ``None`` when logging is switched off."""
    override = os.environ.get("SEOHEAD_RUN_LOG")
    try:
        if override:
            if override.strip().lower() in ("off", "0", "none", "false"):
                return None
            return Path(override).expanduser()
        return Path(DEFAULT_PATH).expanduser()
    except (OSError, ValueError):
        # A malformed override must silence the journal, not stop the tool.
        return None


def _redact(value: Any) -> Any:
    """Shorten a value for the journal without changing its meaning."""
    if isinstance(value, str):
        return value if len(value) <= MAX_VALUE_CHARS else value[:MAX_VALUE_CHARS] + "…"
    if isinstance(value, (list, tuple)):
        shown = [_redact(v) for v in list(value)[:10]]
        if len(value) > 10:
            shown.append(f"…+{len(value) - 10} more")
        return shown
    if isinstance(value, dict):
        return {k: _redact(v) for k, v in value.items()}
    return value


def safe_arguments(arguments: dict[str, Any] | None) -> dict[str, Any]:
    """Drop credentials, shorten the rest.

    A journal that leaks an API key is worse than no journal, and the leak would
    be silent: nothing about a log file suggests it holds secrets.
    """
    out: dict[str, Any] = {}
    for name, value in (arguments or {}).items():
        if any(hint in name.lower() for hint in SECRET_HINTS):
            out[name] = "[redacted]"
        else:
            out[name] = _redact(value)
    return out


def fingerprint(tool: str, arguments: dict[str, Any] | None) -> str:
    """Stable identity for "the same call again", for later reuse decisions."""
    payload = json.dumps(
        {"tool": tool, "arguments": safe_arguments(arguments)}, sort_keys=True, ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def record(entry: dict[str, Any]) -> dict[str, Any]:
    """Append one entry. Never raises: journaling must not break a run."""
    path = log_path()
    if path is None:
        return entry
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except (OSError, ValueError):
        # An unwritable journal is a degraded observation, not a failed audit.
        # ValueError as well as OSError: an invalid path (a null byte from a bad
        # environment variable) raises before the filesystem is ever touched.
        pass
    return entry


@contextmanager
def journal(interface: str, tool: str, arguments: dict[str, Any] | None = None):
    """Record one call, whether it succeeds or raises.

    ``yield``s a mutable dict; a caller may add result facts to it (URLs crawled,
    output directory) and they are written alongside the call.
    """
    started = time.time()
    monotonic = time.monotonic()
    facts: dict[str, Any] = {}
    error: str | None = None
    try:
        yield facts
    except BaseException as exc:  # recorded, then re-raised unchanged
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        record(
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
                "interface": interface,
                "tool": tool,
                "arguments": safe_arguments(arguments),
                "fingerprint": fingerprint(tool, arguments),
                "duration_s": round(time.monotonic() - monotonic, 3),
                "ok": error is None,
                "error": error,
                **facts,
            }
        )


def journaled(tool: str, function):
    """Wrap a handler so every call through any interface is recorded once."""
    import functools

    @functools.wraps(function)
    def wrapper(**kwargs):
        with journal(current_interface(), tool, kwargs) as facts:
            result = function(**kwargs)
            if isinstance(result, dict):
                # Enough to answer "what did that run do" without opening the
                # report. The tool's own "ok" is kept under a separate name: the
                # journal's "ok" means the call did not raise, which is a
                # different claim from the tool reporting a usable result.
                for key in ("urls_collected", "out_dir", "count"):
                    if key in result:
                        facts[key] = result[key]
                if "ok" in result:
                    facts["result_ok"] = result["ok"]
            return result

    return wrapper


def read_entries(limit: int = 100) -> list[dict[str, Any]]:
    """Most recent entries first. A missing journal is empty, not an error."""
    path = log_path()
    if path is None or not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError):
        return []
    entries: list[dict[str, Any]] = []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue  # a truncated final line must not hide the rest
        if len(entries) >= limit:
            break
    return entries
