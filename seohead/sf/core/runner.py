"""ExportRunner — mode A: drive the Screaming Frog CLI to produce exports.

Requires a licensed SF install (headless export and ``--load-crawl`` are paid
features). Builds the ``--export-tabs`` / ``--bulk-export`` /
``--save-report`` command from the configured profile and runs it headless.
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
from collections.abc import Iterator
from urllib.parse import urlsplit

from seohead.recon.net import validate_url

from ..config import deep_merge

# Executable names across platforms (Windows GUI ships a separate *Cli.exe;
# the macOS .app bundle ships ScreamingFrogSEOSpiderLauncher instead of *Cli).
SF_EXE_NAMES = (
    "ScreamingFrogSEOSpiderCli.exe",
    "ScreamingFrogSEOSpiderCli",
    "ScreamingFrogSEOSpiderLauncher",
    "screamingfrogseospider",
    "screaming-frog-seo-spider",
)

# Glob patterns for standard install locations on Windows / macOS / Linux.
# ``Program Files*`` matches both "Program Files" and "Program Files (x86)".
# On macOS the CLI entry point is the app-bundle *Launcher* (SF 19.x); the
# *Cli name is kept first in case a future build ships a dedicated binary.
SF_GLOBS = (
    r"C:\Program Files*\Screaming Frog SEO Spider\ScreamingFrogSEOSpiderCli.exe",
    r"C:\Program Files*\Screaming Frog SEO Spider\*Cli.exe",
    "/Applications/Screaming Frog SEO Spider.app/Contents/MacOS/ScreamingFrogSEOSpiderCli",
    "/Applications/Screaming Frog SEO Spider.app/Contents/MacOS/ScreamingFrogSEOSpiderLauncher",
    os.path.expanduser(
        "~/Applications/Screaming Frog SEO Spider.app/Contents/MacOS/ScreamingFrogSEOSpiderCli"
    ),
    os.path.expanduser(
        "~/Applications/Screaming Frog SEO Spider.app/Contents/MacOS/ScreamingFrogSEOSpiderLauncher"
    ),
    "/usr/bin/screamingfrogseospider",
    "/usr/local/bin/screamingfrogseospider",
    "/opt/screamingfrogseospider/screamingfrogseospider",
    "/snap/bin/screaming-frog-seo-spider",
)


def _candidate_paths(config: dict, override: str | None) -> Iterator[str]:
    """Yield every place the SF CLI could live, most specific first."""
    sf = config.get("sf_cli", {})
    yield from (
        override,
        os.environ.get("SF_CLI"),
        os.environ.get("SCREAMINGFROG_CLI"),
        sf.get("path"),
    )
    yield from sf.get("search_paths", [])
    for name in SF_EXE_NAMES:  # anything on PATH
        hit = shutil.which(name)
        if hit:
            yield hit
    for pattern in SF_GLOBS:  # standard install dirs (incl. versioned/x86)
        yield from glob.glob(pattern)


def find_sf_cli(config: dict, override: str | None = None) -> str | None:
    """Locate the Screaming Frog CLI anywhere it could reasonably be; None if absent."""
    seen: set[str] = set()
    for path in _candidate_paths(config, override):
        if not path or path in seen:
            continue
        seen.add(path)
        if os.path.isfile(path):
            return path
    return None


def resolve_cli(config: dict, override: str | None = None) -> str:
    path = find_sf_cli(config, override)
    if path:
        return path
    raise FileNotFoundError(
        "Screaming Frog CLI not found. Searched --sf-cli, $SF_CLI, config sf_cli.path, "
        "PATH, and standard install dirs (Program Files / Applications / /usr /opt /snap). "
        "Set sf_cli.path in config or pass --sf-cli, or use mode B (--exports-dir). "
        "Mode A also needs a licensed SF."
    )


def build_command(
    cli_path: str, *, source_arg: str, source_value: str, output_folder: str, config: dict
) -> list[str]:
    sf = config.get("sf_cli", {})
    exports = config.get("exports", {})
    cmd = [
        cli_path,
        "--headless",
        source_arg,
        source_value,
        "--output-folder",
        output_folder,
        "--export-format",
        sf.get("export_format", "csv"),
        "--timestamped-output",
    ]
    # Auto-use the audit config only if it actually exists (set-up-once, all sites);
    # silently run with SF defaults otherwise — never break the crawl on a missing file.
    cfg_path = sf.get("seospiderconfig")
    if cfg_path and os.path.isfile(cfg_path):
        cmd += ["--config", os.path.abspath(cfg_path)]

    # For Basic-Auth staging environments and form-based logins, SF accepts an
    # authentication profile previously saved from the GUI under
    # Config -> Authentication -> Profiles -> Save.
    auth_path = sf.get("auth_config")
    if auth_path and os.path.isfile(auth_path):
        cmd += ["--auth-config", os.path.abspath(auth_path)]

    tabs = list(exports.get("tabs", []))
    bulk = list(exports.get("bulk", []))
    if exports.get("fetch_all_inlinks"):
        bulk = ["All Inlinks", *bulk]
    reports = list(exports.get("reports", []))

    if tabs:
        cmd += ["--export-tabs", ",".join(tabs)]
    if bulk:
        cmd += ["--bulk-export", ",".join(bulk)]
    if reports:
        cmd += ["--save-report", ",".join(reports)]
    return cmd


def _apply_rate_limit(config: dict, output_folder: str, log) -> dict:
    """Build and inject a rate-limited .seospiderconfig when requested.

    The SF CLI has no speed flag, so the limit can only live in its config; see
    :mod:`spiderconfig` for the serialization details. If a safe config cannot
    be built, fail with an explanation instead of crawling a third-party site at
    full speed after the caller explicitly requested throttling.
    """
    sf = config.get("sf_cli", {})
    rate = sf.get("max_urls_per_second")
    if not rate:
        return config
    from .spiderconfig import build_throttled_config

    dest = os.path.join(output_folder, "throttled.seospiderconfig")
    path = build_throttled_config(
        dest, urls_per_second=float(rate), base=sf.get("seospiderconfig") or None
    )
    log(f"[runner] crawl rate limited to {rate} URLs/s via config {path}")
    return deep_merge(config, {"sf_cli": {"seospiderconfig": path}})


def run_sf(
    *,
    mode: str,
    source: str,
    output_folder: str,
    config: dict,
    cli_override: str | None = None,
    log=print,
) -> str:
    """Run SF headless and return the folder containing the fresh exports.

    ``mode`` is one of ``crawl`` (url), ``crawl-list`` (file), ``load-crawl``
    (.seospider). SF writes a timestamped subfolder; we return it.
    """
    if mode == "crawl":
        trusted_proxy = config.get("sf_cli", {}).get("_trusted_loopback_proxy")
        source_parts = urlsplit(source)
        proxy_parts = urlsplit(trusted_proxy or "")
        is_trusted_loopback = (
            bool(trusted_proxy)
            and source_parts.scheme == proxy_parts.scheme == "http"
            and source_parts.hostname == proxy_parts.hostname == "127.0.0.1"
            and source_parts.port == proxy_parts.port
        )
        if not is_trusted_loopback:
            validate_url(source)
    cli = resolve_cli(config, cli_override)
    arg = {"crawl": "--crawl", "crawl-list": "--crawl-list", "load-crawl": "--load-crawl"}[mode]
    # SF starts in its own working directory and does not resolve a relative
    # --output-folder as expected. It emits "FATAL - Directory does not exist"
    # yet still exits with status 0, causing export loading to fail later.
    output_folder = os.path.abspath(output_folder)
    os.makedirs(output_folder, exist_ok=True)
    config = _apply_rate_limit(config, output_folder, log)
    cmd = build_command(
        cli, source_arg=arg, source_value=source, output_folder=output_folder, config=config
    )
    log(f"[runner] {' '.join(cmd)}")
    timeout = config.get("sf_cli", {}).get("timeout_minutes", 30) * 60
    try:
        proc = subprocess.run(
            cmd, timeout=timeout, capture_output=True, text=True, stdin=subprocess.DEVNULL
        )
    except subprocess.TimeoutExpired as err:
        raise RuntimeError(
            f"Screaming Frog CLI timed out after {timeout // 60} min. "
            "Increase sf_cli.timeout_minutes or narrow the crawl."
        ) from err
    if proc.returncode != 0:
        raise RuntimeError(
            f"Screaming Frog CLI failed (exit {proc.returncode}).\n{(proc.stderr or '')[-4000:]}"
        )
    exports_dir = _latest_export_dir(output_folder)
    if not _has_exports(exports_dir):
        # SF may return status 0 even after a startup failure, such as a FATAL
        # output-directory error. Without this guard, callers see "Required
        # export 'internal_all' not found" and investigate exports instead of the
        # failed process launch.
        tail = ((proc.stdout or "") + (proc.stderr or "")).strip()[-2000:]
        raise RuntimeError(
            f"Screaming Frog CLI exited 0 but wrote no exports to {exports_dir} — "
            "the crawl produced nothing, or SF never started (check the output below).\n"
            f"SF output (tail):\n{tail or '(empty)'}"
        )
    return exports_dir


def _has_exports(folder: str) -> bool:
    """Return whether the folder contains any SF export from a completed crawl."""
    try:
        names = os.listdir(folder)
    except OSError:
        return False
    return any(n.lower().endswith((".csv", ".xlsx", ".xls", ".gsheet")) for n in names)


def _latest_export_dir(output_folder: str) -> str:
    """SF writes a timestamped subfolder; pick the newest, else the folder itself."""
    subdirs = [
        os.path.join(output_folder, d)
        for d in os.listdir(output_folder)
        if os.path.isdir(os.path.join(output_folder, d))
    ]
    if not subdirs:
        return output_folder
    return max(subdirs, key=os.path.getmtime)
