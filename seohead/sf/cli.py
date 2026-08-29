"""Console interface for crawl audits and task generation.

This module deliberately remains a thin argument-mapping layer over
``core.run_audit`` so CLI concerns cannot leak into the audit engine.
"""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .config import load_config
from .core.audit import run_audit
from .reporters import write_json, write_markdown
from .reporters.json_reporter import to_dict
from .tasks import build_tasks, write_tasks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sf-analyzer",
        description=(
            "Generate a machine-readable SEO audit from a Screaming Frog crawl "
            "(audit.json + audit.md)."
        ),
    )
    parser.add_argument("--version", action="version", version=f"sf-analyzer {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run an audit")
    src = run.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--load-crawl",
        metavar="FILE.seospider",
        help="Mode A: open a saved crawl through the licensed SF CLI",
    )
    src.add_argument(
        "--crawl",
        metavar="URL",
        help="Mode A: crawl a site from scratch through the licensed SF CLI",
    )
    src.add_argument(
        "--crawl-list", metavar="FILE", help="Mode A: crawl a URL list through the licensed SF CLI"
    )
    src.add_argument(
        "--exports-dir",
        metavar="DIR",
        help="Mode B: read an existing directory of SF CSV/XLSX exports",
    )

    run.add_argument("--out", default="report", help="Report output directory (default: ./report)")
    run.add_argument(
        "--profile",
        choices=["lite", "full", "custom"],
        default=None,
        help="Audit/export profile: full (default, maximum coverage), lite, or custom",
    )
    run.add_argument("--config", default="config.json", help="Path to config.json")
    run.add_argument(
        "--auth-config",
        default=None,
        help=(
            "SF form-authentication profile (.seospiderauthconfig) for protected "
            "staging or production environments"
        ),
    )
    run.add_argument(
        "--auth",
        default=None,
        metavar="USER:PASS",
        help=(
            "HTTP Basic credentials in USER:PASS form; may be visible in shell history/process "
            "lists, so prefer an isolated transient session"
        ),
    )
    run.add_argument(
        "--sf-cli", default=None, help="Explicit path to the Screaming Frog CLI/launcher executable"
    )
    run.add_argument(
        "--max-urls-per-second",
        type=float,
        default=None,
        metavar="N",
        help=(
            "Limit the Mode A crawl request rate. The tool gives SF a derived "
            ".seospiderconfig containing this limit, so an existing base config "
            "is required (sf_cli.seospiderconfig or a previous crawl). Thread "
            "count is left unchanged because the request-rate cap is stricter."
        ),
    )
    run.add_argument(
        "--sitemap",
        default=None,
        help="Explicit sitemap.xml URL (otherwise discover it from robots.txt)",
    )
    run.add_argument(
        "--fetch-all-inlinks",
        action="store_true",
        help="Fetch the large All Inlinks export in Mode A",
    )
    run.add_argument(
        "--live-recheck",
        dest="live_recheck",
        action="store_true",
        help="Enable opt-in network rechecks for sitemap and robots data",
    )
    run.add_argument("--no-live-recheck", dest="live_recheck", action="store_false")
    run.set_defaults(live_recheck=None)
    run.add_argument(
        "--format", default="json,md", help="Comma-separated report formats to generate: json,md"
    )
    run.add_argument(
        "--tasks",
        action="store_true",
        help="Also generate the prioritized tasks.json + tasks.md backlog",
    )
    run.add_argument(
        "--fail-on",
        choices=["critical", "warning", "none"],
        default="none",
        help="Return a non-zero exit code when this severity is present (for CI)",
    )
    run.add_argument("-v", "--verbose", action="store_true")
    run.add_argument("-q", "--quiet", action="store_true")

    # `tasks` builds a backlog from an existing audit.json without rerunning the audit.
    tasks = sub.add_parser("tasks", help="Build a prioritized task backlog from audit.json")
    tasks.add_argument("--json", dest="audit_json", required=True, help="Path to audit.json")
    tasks.add_argument(
        "--out", default="report", help="Output directory for tasks.json and tasks.md"
    )
    tasks.add_argument(
        "--config",
        default="config.json",
        help="Path to config.json containing the task-pipeline settings",
    )
    tasks.add_argument("-q", "--quiet", action="store_true")

    # `doctor` reports SF discovery and optional dependency availability.
    doc = sub.add_parser("doctor", help="Diagnose SF CLI discovery and dependency availability")
    doc.add_argument("--config", default="config.json", help="Path to config.json")
    doc.add_argument(
        "--sf-cli", default=None, help="Explicit SF CLI path to validate before searching elsewhere"
    )
    return parser


def _run_doctor(args) -> int:
    from .core.runner import SF_GLOBS, find_sf_cli

    cfg = load_config(args.config)
    sf = find_sf_cli(cfg, args.sf_cli)
    print("Screaming Frog CLI:", sf or "NOT FOUND")
    if not sf:
        print("  searched: --sf-cli, $SF_CLI, config sf_cli.path, PATH, and:")
        for g in SF_GLOBS:
            print("   -", g)
        print("  → set sf_cli.path in config.json, set $SF_CLI, or pass --sf-cli;")
        print("    otherwise use Mode B: sf-analyzer run --exports-dir ./exports")
    print("\nDependencies:")
    for mod, what in (
        ("pandas", "core"),
        ("lxml", "core"),
        ("jsonschema", "schema"),
        ("openpyxl", "xlsx"),
        ("advertools", "sitemap (optional)"),
        ("mcp", "MCP server (optional)"),
    ):
        try:
            __import__(mod)
            print(f"  [ok] {mod} ({what})")
        except ImportError:
            print(f"  [--] {mod} ({what})")
    return 0 if sf else 1


def _resolve_input(args: argparse.Namespace) -> tuple[str, str | None, str | None]:
    if args.load_crawl:
        return "load-crawl", args.load_crawl, None
    if args.crawl:
        return "crawl", args.crawl, None
    if args.crawl_list:
        return "crawl-list", args.crawl_list, None
    return "parse-exports", None, args.exports_dir


def _run_tasks(args) -> int:
    import json

    try:
        with open(args.audit_json, encoding="utf-8") as fh:
            audit = json.load(fh)
    except (OSError, ValueError) as err:
        print(f"error: cannot read audit json: {err}", file=sys.stderr)
        return 1
    cfg = load_config(args.config)
    backlog = build_tasks(audit, cfg)
    os.makedirs(args.out, exist_ok=True)
    jp, mp = write_tasks(
        backlog, os.path.join(args.out, "tasks.json"), os.path.join(args.out, "tasks.md")
    )
    if not args.quiet:
        s = backlog["summary"]
        print(
            f"tasks={s['tasks_total']} "
            f"{' '.join(f'{k}={v}' for k, v in sorted(s['by_priority'].items()))}"
        )
        print(f"[out] {jp}\n[out] {mp}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "tasks":
        return _run_tasks(args)
    if args.command == "doctor":
        return _run_doctor(args)
    if args.command != "run":
        return 1

    def log(msg: str) -> None:
        if args.verbose and not args.quiet:  # progress only when asked
            print(msg, file=sys.stderr)

    input_mode, source, exports_dir = _resolve_input(args)
    try:
        # Protected environments support two distinct authentication mechanisms.
        # Form login remains an SF-owned profile file; Basic authentication is
        # implemented at runtime without persisting credentials in the config.
        cfg_overrides: dict = {}
        if getattr(args, "auth_config", None):
            cfg_overrides.setdefault("sf_cli", {})["auth_config"] = args.auth_config
        if getattr(args, "max_urls_per_second", None):
            cfg_overrides.setdefault("sf_cli", {})["max_urls_per_second"] = args.max_urls_per_second
        # SF does not reliably accept Basic credentials in the URL or through a
        # CLI flag. A loopback proxy therefore injects the Authorization header;
        # exported URLs are rewritten back to the original origin afterwards.
        auth_proxy = None
        if getattr(args, "auth", None) and source and source.startswith("http"):
            from .core.auth_proxy import AuthProxy, parse_auth

            try:
                user, password = parse_auth(args.auth)
            except ValueError as error:
                raise SystemExit(str(error)) from error

            auth_proxy = AuthProxy(source, user, password)
            proxy_base = auth_proxy.start()
            source = source.replace(auth_proxy.origin, proxy_base)
            cfg_overrides.setdefault("sf_cli", {})["_trusted_loopback_proxy"] = proxy_base
            log(f"[cli] protected site: crawling through local auth proxy {proxy_base}")

        result = run_audit(
            input_mode=input_mode,
            source=source,
            exports_dir=exports_dir,
            config_path=args.config,
            config_overrides=cfg_overrides or None,
            sf_cli=args.sf_cli,
            sitemap_url=args.sitemap,
            profile=args.profile,
            fetch_all_inlinks=args.fetch_all_inlinks or None,
            live_recheck=args.live_recheck,
            output_dir=os.path.join(args.out, "exports"),
            url_rewrite=(auth_proxy.base_url, auth_proxy.origin) if auth_proxy else None,
            log=log,
        )
        if auth_proxy:
            auth_proxy.stop()
    # The CLI converts any core failure into a concise user-facing error; verbose
    # mode still exposes the traceback for diagnosis.
    except Exception as err:
        print(f"error: {err}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1

    formats = {f.strip().lower() for f in args.format.split(",") if f.strip()}
    os.makedirs(args.out, exist_ok=True)
    if "json" in formats:
        path = write_json(result, os.path.join(args.out, "audit.json"))
        log(f"[out] {path}")
    if "md" in formats:
        path = write_markdown(result, os.path.join(args.out, "audit.md"))
        log(f"[out] {path}")
    if args.tasks:
        backlog = build_tasks(to_dict(result), load_config(args.config))
        jp, mp = write_tasks(
            backlog, os.path.join(args.out, "tasks.json"), os.path.join(args.out, "tasks.md")
        )
        log(f"[out] {jp}")
        log(f"[out] {mp}")

    if not args.quiet:
        sev = result.summary["by_severity"]
        print(
            f"health={result.summary['health_score']} "
            f"critical={sev['critical']} warning={sev['warning']} notice={sev['notice']} "
            f"issues={result.summary['totals']['issues_total']}"
        )

    if args.fail_on == "critical" and result.summary["by_severity"]["critical"] > 0:
        return 2
    if args.fail_on == "warning" and (
        result.summary["by_severity"]["critical"] > 0
        or result.summary["by_severity"]["warning"] > 0
    ):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
