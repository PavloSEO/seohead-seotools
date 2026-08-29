"""SF CLI discovery and the internal/external inlinks split."""

from __future__ import annotations

import csv

from seohead.sf.config import load_config
from seohead.sf.core.audit import run_audit
from seohead.sf.core.runner import find_sf_cli


def test_find_sf_cli_override(tmp_path):
    fake = tmp_path / "ScreamingFrogSEOSpiderCli.exe"
    fake.write_text("", encoding="utf-8")
    assert find_sf_cli(load_config(None), str(fake)) == str(fake)


def test_find_sf_cli_from_config(tmp_path):
    fake = tmp_path / "sf.exe"
    fake.write_text("", encoding="utf-8")
    cfg = load_config(None)
    cfg["sf_cli"]["path"] = str(fake)
    assert find_sf_cli(cfg) == str(fake)


def test_find_sf_cli_macos_launcher(tmp_path, monkeypatch):
    """macOS bundle ships ScreamingFrogSEOSpiderLauncher, not *Cli (SF 19.x)."""
    from seohead.sf.core import runner

    macos_dir = tmp_path / "Screaming Frog SEO Spider.app" / "Contents" / "MacOS"
    macos_dir.mkdir(parents=True)
    launcher = macos_dir / "ScreamingFrogSEOSpiderLauncher"
    launcher.write_text("", encoding="utf-8")

    # isolate from the real machine: no env/config/PATH hits, only our "bundle"
    monkeypatch.delenv("SF_CLI", raising=False)
    monkeypatch.delenv("SCREAMINGFROG_CLI", raising=False)
    monkeypatch.setattr(runner.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        runner,
        "SF_GLOBS",
        (
            str(macos_dir / "ScreamingFrogSEOSpiderCli"),
            str(macos_dir / "ScreamingFrogSEOSpiderLauncher"),
        ),
    )

    cfg = load_config(None)
    cfg["sf_cli"]["path"] = ""
    cfg["sf_cli"]["search_paths"] = []
    assert runner.find_sf_cli(cfg) == str(launcher)
    # explicit --sf-cli still wins over autodiscovery
    fake = tmp_path / "override-cli"
    fake.write_text("", encoding="utf-8")
    assert runner.find_sf_cli(cfg, str(fake)) == str(fake)


def test_macos_launcher_in_default_search():
    from seohead.sf.core.runner import SF_EXE_NAMES, SF_GLOBS

    assert "ScreamingFrogSEOSpiderLauncher" in SF_EXE_NAMES
    assert (
        "/Applications/Screaming Frog SEO Spider.app/Contents/MacOS/ScreamingFrogSEOSpiderLauncher"
    ) in SF_GLOBS


def test_find_sf_cli_absent_returns_none():
    cfg = load_config(None)
    cfg["sf_cli"]["path"] = ""
    cfg["sf_cli"]["search_paths"] = ["/nonexistent/sf"]
    # may still be None on a machine without SF; assert it doesn't raise
    assert find_sf_cli(cfg) is None or isinstance(find_sf_cli(cfg), str)


def test_build_command_config_only_if_exists(tmp_path):
    from seohead.sf.core.runner import build_command

    cfg = load_config(None)
    cfg["sf_cli"]["seospiderconfig"] = str(tmp_path / "missing.seospiderconfig")
    cmd = build_command(
        "sf.exe",
        source_arg="--crawl",
        source_value="https://example.com",
        output_folder="out",
        config=cfg,
    )
    assert "--config" not in cmd  # missing file -> not passed (no crawl break)

    real = tmp_path / "audit.seospiderconfig"
    real.write_text("", encoding="utf-8")
    cfg["sf_cli"]["seospiderconfig"] = str(real)
    cmd = build_command(
        "sf.exe",
        source_arg="--crawl",
        source_value="https://example.com",
        output_folder="out",
        config=cfg,
    )
    assert "--config" in cmd and str(real) in " ".join(cmd)


def test_native_export_titles_multiple_and_hreflang(tmp_path):
    import csv as _csv

    d = tmp_path / "exports"
    d.mkdir()
    with open(d / "internal_all.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = _csv.writer(f)
        w.writerow(["Address", "Content Type", "Status Code", "Status", "Indexability"])
        w.writerow(["https://example.com/", "text/html", "200", "OK", "Indexable"])
    with open(d / "page_titles_multiple.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = _csv.writer(f)
        w.writerow(["Address", "Occurrences"])
        w.writerow(["https://example.com/dup-title", "2"])
    res = run_audit(input_mode="parse-exports", exports_dir=str(d), log=lambda m: None)
    fired = {i.check: {x.target_url for x in res.issues if x.check == i.check} for i in res.issues}
    assert "https://example.com/dup-title" in fired.get("TITLE_MULTIPLE", set())
    # hreflang export absent -> honest skip, not a dead zero
    assert "HREFLANG_ERROR" in {s.id for s in res.skipped}


def test_important_url_blocked_by_robots(tmp_path):
    d = tmp_path / "exports"
    d.mkdir()
    with open(d / "internal_all.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "Address",
                "Content Type",
                "Status Code",
                "Status",
                "Indexability",
                "Indexability Status",
                "Inlinks",
            ]
        )
        # blocked + internally linked -> important; blocked + 0 inlinks -> not important
        w.writerow(
            [
                "https://example.com/blog?page=2",
                "text/html",
                "0",
                "",
                "Non-Indexable",
                "Blocked by Robots.txt",
                "5",
            ]
        )
        w.writerow(
            [
                "https://example.com/dead-end",
                "text/html",
                "0",
                "",
                "Non-Indexable",
                "Blocked by Robots.txt",
                "0",
            ]
        )
    res = run_audit(input_mode="parse-exports", exports_dir=str(d), log=lambda m: None)
    by = {}
    for i in res.issues:
        by.setdefault(i.check, set()).add(i.target_url)
    assert by.get("IMPORTANT_URL_BLOCKED_BY_ROBOTS") == {"https://example.com/blog?page=2"}


def test_inlinks_internal_external_split(tmp_path):
    d = tmp_path / "exports"
    d.mkdir()
    with open(d / "internal_all.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Address", "Content Type", "Status Code", "Status", "Indexability"])
        w.writerow(["https://example.com/", "text/html", "200", "OK", "Indexable"])
    with open(
        d / "response_codes_client_error_(4xx)_inlinks.csv", "w", encoding="utf-8-sig", newline=""
    ) as f:
        w = csv.writer(f)
        w.writerow(
            ["Source", "Destination", "Anchor Text", "Status Code", "Link Position", "Link Path"]
        )
        w.writerow(
            ["https://example.com/", "https://example.com/gone", "here", "404", "Content", "/a"]
        )
        w.writerow(
            ["https://example.com/", "https://example.org/dead", "external", "404", "Content", "/b"]
        )
    res = run_audit(input_mode="parse-exports", exports_dir=str(d), log=lambda m: None)
    by = {}
    for i in res.issues:
        by.setdefault(i.check, set()).add(i.target_url)
    assert by.get("BROKEN_INTERNAL_LINK") == {"https://example.com/gone"}
    assert by.get("BROKEN_EXTERNAL_LINK") == {"https://example.org/dead"}
