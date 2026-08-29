"""Apply a Screaming Frog crawl-rate limit in headless mode.

The SF CLI has no speed option. It only accepts
``--config <file.seospiderconfig>``, and the config itself must be created in the
GUI (Config → Speed → File → Config → Save As). The only safe headless approach
is to start from an existing config and update the two fields in
``seo.spider.config.SpiderPerformanceConfig`` precisely.

In the Java serialization stream, this class declares exactly two fields in the
following order::

    Z  mLimitPerformance        (boolean, 1 byte)
    D  mUrlRequestsPerSecond    (double,  8 bytes, big-endian)

Their values immediately follow ``TC_ENDBLOCKDATA TC_NULL`` (``b"xp"``), which
terminates the class descriptor. The patch changes exactly nine bytes and
nothing else, preserving the stream structure so SF can read its own file.

An explicit limitation: this code does not modify ``mMaxThreads``. That integer
is one of roughly ten primitive fields in another class, and its offset cannot
be determined without parsing that descriptor fully. Guessing an offset could
silently corrupt the config. The requests-per-second limit is already the more
restrictive control over crawl traffic.
"""

from __future__ import annotations

import glob
import os
import struct

PERF_FIELD = b"mUrlRequestsPerSecond"
PERF_CLASS = b"seo.spider.config.SpiderPerformanceConfig"
FIELDS_END = b"xp"  # TC_ENDBLOCKDATA + TC_NULL

# Match the practical range exposed by the SF GUI: 0.1 to 1,000 URLs per second.
MIN_RATE = 0.1
MAX_RATE = 1000.0

# SF stores the latest crawl config at these locations. The serialized format is
# the same as a saved .seospiderconfig file.
CRAWL_CONFIG_GLOBS = (
    os.path.expanduser(
        "~/.ScreamingFrogSEOSpider/ProjectInstanceData/*/serialised_data/spiderconfig"
    ),
    os.path.expanduser("~/.ScreamingFrogSEOSpider/spiderconfig"),
)


def _perf_offsets(blob: bytes) -> tuple[int, int]:
    """Return the flag and double offsets in SpiderPerformanceConfig.

    Raise :class:`ValueError` when the stream layout is not the exact structure
    this implementation can patch. Never guess offsets in an unknown config.
    """
    field = blob.find(PERF_FIELD)
    if field < 0:
        raise ValueError(
            f"config does not contain {PERF_FIELD.decode()} — "
            "it is not a serialized Screaming Frog config or uses another format version"
        )
    end = blob.find(FIELDS_END, field)
    if end < 0:
        raise ValueError("SpiderPerformanceConfig descriptor is unterminated — config is corrupt")
    flag_at = end + len(FIELDS_END)
    double_at = flag_at + 1
    if double_at + 8 > len(blob):
        raise ValueError("config ends inside the speed block — file is corrupt")
    if blob[flag_at] not in (0, 1):
        raise ValueError(
            f"mLimitPerformance contains {blob[flag_at]:#02x}, expected 0 or 1 — "
            "the config layout does not match and cannot be patched safely"
        )
    return flag_at, double_at


def read_speed(blob: bytes) -> tuple[bool, float]:
    """Read ``(limit_enabled, URLs_per_second)`` from a config blob."""
    flag_at, double_at = _perf_offsets(blob)
    return bool(blob[flag_at]), struct.unpack(">d", blob[double_at : double_at + 8])[0]


def patch_speed(blob: bytes, urls_per_second: float) -> bytes:
    """Enable and set the crawl-rate limit without performing I/O."""
    rate = float(urls_per_second)
    if not MIN_RATE <= rate <= MAX_RATE:
        raise ValueError(f"rate {rate} is outside the allowed {MIN_RATE}..{MAX_RATE} URLs/s")
    flag_at, double_at = _perf_offsets(blob)
    out = bytearray(blob)
    out[flag_at] = 1
    out[double_at : double_at + 8] = struct.pack(">d", rate)
    patched = bytes(out)
    # Trust the patch only after a round-trip through the same strict parser.
    enabled, written = read_speed(patched)
    if not enabled or abs(written - rate) > 1e-9:
        raise ValueError("speed patch failed round-trip validation — file was not written")
    return patched


def find_base_config(explicit: str | None = None) -> str | None:
    """Find an explicit base config, or fall back to the latest crawl config."""
    if explicit and os.path.isfile(explicit):
        return explicit
    found: list[str] = []
    for pattern in CRAWL_CONFIG_GLOBS:
        found.extend(p for p in glob.glob(pattern) if os.path.isfile(p))
    if not found:
        return None
    return max(found, key=os.path.getmtime)


def build_throttled_config(dest: str, *, urls_per_second: float, base: str | None = None) -> str:
    """Build a rate-limited .seospiderconfig and return its absolute path."""
    source = find_base_config(base)
    if not source:
        raise RuntimeError(
            "cannot apply a crawl-rate limit because no base Screaming Frog config was found. "
            "Save any config from the GUI (Config → File → Config → Save As) and set its "
            "path as sf_cli.seospiderconfig in config.json, or run one crawl in the GUI so "
            "SF creates a reusable config automatically. Without a base file, the limit "
            "cannot be set; the toolkit will not crawl a third-party site at full speed "
            "after a rate limit was explicitly requested."
        )
    with open(source, "rb") as fh:
        blob = fh.read()
    patched = patch_speed(blob, urls_per_second)
    os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
    with open(dest, "wb") as fh:
        fh.write(patched)
    return os.path.abspath(dest)
