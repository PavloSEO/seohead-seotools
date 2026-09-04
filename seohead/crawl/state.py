"""Durable crawl checkpoint: the frontier, seen-set and depth an interrupted
crawl needs to resume instead of restarting.

Plain JSON only, deliberately. A queue deserialised with pickle, marshal, or a
YAML loader with object tags is arbitrary code execution the moment the state
directory is writable by anything else — which a resumable crawl's state
directory usually is, sooner or later. A corrupt or hostile file here must
fail into "start fresh", never into "run whatever this file says": ``load``
only ever calls ``json.loads`` and never raises, so there is nothing in this
module a crafted file could make execute.
"""

from __future__ import annotations

import contextlib
import json
import os
import stat
from dataclasses import dataclass, field

SCHEMA_VERSION = "crawl_state.v1"


@dataclass
class CrawlState:
    start_url: str
    queue: list[tuple[str, int]] = field(default_factory=list)
    seen: list[str] = field(default_factory=list)
    max_depth_reached: int = 0
    # Fingerprint of the settings that change what the crawl fetches. A mismatch
    # means the frontier on disk was built under different rules than this
    # invocation is about to apply, so resuming would silently mix them.
    config_fingerprint: str = ""


def ensure_safe_dir(directory: str) -> None:
    """Refuse a world-writable state directory.

    A state directory only stays trustworthy if nothing else on the machine can
    write to it. World-writable turns "resume my crawl" into "load whatever the
    next process to touch this directory left behind".
    """
    os.makedirs(directory, exist_ok=True)
    mode = os.stat(directory).st_mode
    if mode & stat.S_IWOTH:
        raise PermissionError(f"refusing a world-writable crawl state directory: {directory}")


def load(path: str, start_url: str, config_fingerprint: str = "") -> tuple[CrawlState | None, str]:
    """Load a checkpoint, or say why not. Never raises.

    A missing, corrupt or hostile file, a schema mismatch, a different start
    URL, and a changed configuration all mean the same thing to a caller:
    start fresh. Only the note attached explains which.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError:
        return None, "no checkpoint found; starting fresh"
    except (OSError, ValueError):
        # ValueError also catches UnicodeDecodeError, which is what a file full
        # of binary garbage (or a pickle payload) produces here.
        return None, "checkpoint file is unreadable; starting fresh"
    if not isinstance(raw, dict):
        return None, "checkpoint file is not a JSON object; starting fresh"
    if raw.get("schema_version") != SCHEMA_VERSION:
        return None, (
            f"checkpoint schema is {raw.get('schema_version')!r}, "
            f"this build expects {SCHEMA_VERSION!r}; starting fresh"
        )
    if raw.get("start_url") != start_url:
        return None, "checkpoint is for a different start URL; starting fresh"
    if config_fingerprint and raw.get("config_fingerprint") != config_fingerprint:
        return None, "crawl scope or limits changed since the checkpoint; starting fresh"
    try:
        queue = [(str(u), int(d)) for u, d in raw.get("queue") or []]
        seen = [str(u) for u in raw.get("seen") or []]
        depth = int(raw.get("max_depth_reached") or 0)
    except (TypeError, ValueError):
        return None, "checkpoint contents are malformed; starting fresh"
    state = CrawlState(
        start_url=start_url,
        queue=queue,
        seen=seen,
        max_depth_reached=depth,
        config_fingerprint=raw.get("config_fingerprint") or "",
    )
    return state, f"resuming from checkpoint: {len(queue)} URL(s) queued, {len(seen)} seen"


def save(path: str, state: CrawlState) -> None:
    """Write the checkpoint atomically so a crash mid-write cannot corrupt it."""
    payload = {
        "schema_version": SCHEMA_VERSION,
        "start_url": state.start_url,
        "queue": [[u, d] for u, d in state.queue],
        "seen": state.seen,
        "max_depth_reached": state.max_depth_reached,
        "config_fingerprint": state.config_fingerprint,
    }
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    os.replace(tmp_path, path)


def clear(path: str) -> None:
    """Remove a checkpoint once the crawl it describes is genuinely finished."""
    with contextlib.suppress(FileNotFoundError):
        os.remove(path)
