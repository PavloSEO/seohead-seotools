"""Every command shown in the documentation must still run.

``scripts/doc_commands.py`` extracts every ``seohead ...`` invocation from the public
Markdown (README, docs/, skills, examples). This module turns each one into something
runnable entirely offline — URLs point at a loopback fixture server instead of the live
internet, and file/directory arguments point at materialized copies of ``examples/`` —
then either executes it in-process through :func:`seohead.cli.main` (asserting a clean
exit) or, for the handful that fundamentally need infrastructure no local fixture can
stand in for (a real RDAP/DNS ecosystem, a licensed Screaming Frog binary, a paid
provider credential, a server that never returns), parses it with the real argument
parser so a renamed or removed flag still fails the build.

A documented command that no longer works is worse than a missing one, because it is
trusted (issue #22).
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
from pathlib import Path

import pytest

from scripts.doc_commands import extract_commands, to_argv
from tests.doc_fixtures.site_server import run_fixture_site

ROOT = Path(__file__).resolve().parent.parent

# Each needs something a local, credential-free fixture cannot stand in for:
# a real RDAP/WHOIS/DNS ecosystem, a licensed Screaming Frog binary or a captured
# .seospider file, a paid or credentialed external API, or (for `mcp`) a server
# that never returns. Full execution is skipped for these; CLI parseability
# (the flags still exist) is still checked below.
NEEDS_LIVE_INFRASTRUCTURE = {
    "domain-profile",
    "mirror-check",
    "keywords-expand",
    "keywords-seasonality",
    "keywords-exact",
    "serp-fetch",
    "google-keywords",
    "google-serp",
    "metrika-counters",
    "metrika-setup",
    "metrika-report",
    "regions-tree",
    "mcp",
}


# `sf` subcommands that inspect the local Screaming Frog installation itself rather than an
# export: they pass on a developer machine that has SF and fail on a runner that does not,
# which is the difference between an environment and a broken command.
SF_SUBCOMMANDS_NEEDING_AN_INSTALL = {"doctor", "save-config"}


def _is_licensed_sf_mode(argv: list[str]) -> bool:
    """Mode A (`--crawl`) needs the licensed SF CLI; `--load-crawl` needs a real capture;
    `doctor` and `save-config` need an installed Screaming Frog to report on at all."""
    if argv[:1] != ["sf"]:
        return False
    if any(flag in argv for flag in ("--crawl", "--load-crawl")):
        return True
    return argv[1:2] and argv[1] in SF_SUBCOMMANDS_NEEDING_AN_INSTALL


def _substitute(raw: str, base_url: str) -> str:
    """Point every URL/domain placeholder in a documented command at the fixture site."""
    host = base_url.split("//", 1)[1]
    # Longer / prefixed patterns first, so a bare fallback cannot half-rewrite one.
    replacements = [
        ("https://example-msk.example", base_url),
        ("https://example-spb.example", base_url),
        ("https://donor1.example", base_url),
        ("https://donor2.example", base_url),
        ("https://<domain>", base_url),
        ("https://example.org", base_url),
        ("https://example.com", base_url),
        ("<domain>", host),
        ("example.com", host),
        ("<template>", "page"),
        ("./sf-exports", "exports"),
        ("./exports", "exports"),
    ]
    text = raw
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _seed_workdir(tmp_path: Path, base_url: str) -> None:
    """Materialize every fixture a documented command's relative path expects."""
    shutil.copytree(ROOT / "examples", tmp_path / "examples")
    shutil.copytree(ROOT / "examples" / "exports", tmp_path / "exports")
    shutil.copy(ROOT / "examples" / "audit.json", tmp_path / "audit.json")
    shutil.copy(ROOT / "examples" / "audit.json", tmp_path / "old-audit.json")
    shutil.copy(ROOT / "examples" / "audit.json", tmp_path / "new-audit.json")
    shutil.copy(ROOT / "config.example.json", tmp_path / "config.json")
    # A finished, internally consistent crawl output, so a documented `log-scan --run ./run`
    # actually scans something instead of reporting that the directory is empty.
    shutil.copytree(ROOT / "tests" / "doc_fixtures" / "run", tmp_path / "run")
    (tmp_path / "report").mkdir()
    shutil.copy(ROOT / "examples" / "audit.json", tmp_path / "report" / "audit.json")
    (tmp_path / "crawl.json").write_text(json.dumps({"limits": {"max_urls": 5}}), encoding="utf-8")
    (tmp_path / "donors.txt").write_text(f"{base_url}/page\n", encoding="utf-8")
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    shutil.copy(ROOT / "tests" / "doc_fixtures" / "site" / "image.png", images_dir / "image.png")


@pytest.fixture(scope="module")
def fixture_site():
    with run_fixture_site() as base_url:
        yield base_url


def _cases():
    for command in extract_commands(ROOT):
        argv = to_argv(command.raw)
        if not argv:
            continue
        yield pytest.param(command, argv, id=f"{command.source.name}:{command.raw}"[:120])


@pytest.mark.parametrize("command,argv", list(_cases()))
def test_documented_command_executes_or_at_least_still_parses(
    command, argv, fixture_site, tmp_path, monkeypatch
):
    tool = argv[0]
    if tool in NEEDS_LIVE_INFRASTRUCTURE or _is_licensed_sf_mode(argv):
        from seohead.cli import build_parser
        from seohead.sf.cli import build_parser as build_sf_parser

        try:
            if argv[0] == "sf":
                build_sf_parser().parse_args(argv[1:])
            else:
                build_parser().parse_args(argv)
        except SystemExit as exc:
            assert exc.code == 0, (
                f"{command.source.relative_to(ROOT)}: `{command.raw}` no longer parses"
            )
        return

    from seohead.cli import main as cli_main

    _seed_workdir(tmp_path, fixture_site)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SEOHEAD_ALLOW_PRIVATE_NETWORKS", "1")
    # A command with no explicit `echo ... |` payload still probes stdin for JSON
    # input; pytest's own captured stdin raises on read instead of giving EOF, so
    # every case (not only the piped ones) gets a real, harmless stream here.
    monkeypatch.setattr("sys.stdin", io.StringIO(command.stdin or ""))

    substituted = to_argv(_substitute(command.raw, fixture_site))
    if substituted[:1] == ["site-audit"] and "--skip" not in substituted:
        # site-audit's own domain-profile sub-check needs real RDAP; every other
        # site-level tool in it is a plain HTTP GET the fixture server answers.
        substituted += ["--skip", "domain_profile"]

    stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout):
            exit_code = cli_main(substituted)
    except SystemExit as exc:  # --version / --help exit through argparse itself
        exit_code = exc.code if isinstance(exc.code, int) else 1

    assert exit_code == 0, (
        f"{command.source.relative_to(ROOT)}: `{command.raw}` exited {exit_code}: "
        f"{stdout.getvalue()[-2000:]}"
    )


def test_every_documented_command_was_exercised_above():
    """Guards the extractor itself: a doc command that fails to parse must fail loudly,
    not vanish from the parametrized list above."""
    commands = extract_commands(ROOT)
    assert commands, "no documented `seohead` commands were found at all"
    for command in commands:
        to_argv(command.raw)  # raises on the rare unparseable line
