"""Ensure explicit CLI source flags do not consume piped standard input.

The regression surfaced when
``while read u; do seohead parse --url "$u"; done < urls.txt`` consumed the
entire input file during the first iteration.
"""

import io
import json

import pytest

from seohead import cli
from seohead.servers import handlers


class _NeverReadStdin(io.StringIO):
    """Standard input that fails the test if anything attempts to read it."""

    def read(self, *a, **k):  # pragma: no cover - defensive test guard
        raise AssertionError("CLI read stdin even though a source flag was provided")

    def isatty(self):
        return False


def test_parse_with_url_flag_ignores_stdin(monkeypatch, capsys):
    monkeypatch.setattr(cli.sys, "stdin", _NeverReadStdin("https://other.example/\n" * 100))
    monkeypatch.setitem(handlers.HANDLERS, "parse", lambda **kw: {"ok": True, "echo": kw})
    rc = cli.main(["parse", "--url", "https://example.com/"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["echo"]["url"] == "https://example.com/"


def test_duplicate_check_still_reads_piped_stdin(monkeypatch, capsys):
    """Without source flags, piped input continues to work as before."""
    payload = {"items": [{"id": "a", "text": "x " * 50}], "threshold": 0.9}
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setitem(handlers.HANDLERS, "duplicate_check", lambda **kw: {"ok": True, "echo": kw})
    rc = cli.main(["duplicate-check"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["echo"]["items"] and out["echo"]["threshold"] == 0.9


def test_images_optimize_output_dir_maps_to_settings(monkeypatch, capsys):
    monkeypatch.setattr(cli.sys, "stdin", _NeverReadStdin())
    monkeypatch.setitem(handlers.HANDLERS, "images_optimize", lambda **kw: {"ok": True, "echo": kw})
    rc = cli.main(["images-optimize", "--files", "a.png,b.png", "--output-dir", "/tmp/out"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["echo"]["files"] == ["a.png", "b.png"]
    assert out["echo"]["settings"]["out_dir"] == "/tmp/out"


def test_duplicate_check_fingerprints_flag(monkeypatch, capsys):
    payload = {"items": [{"id": "a", "text": "x " * 50}]}
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setitem(handlers.HANDLERS, "duplicate_check", lambda **kw: {"ok": True, "echo": kw})
    rc = cli.main(["duplicate-check", "--fingerprints"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["echo"]["with_fingerprints"] is True


@pytest.mark.parametrize(
    ("command", "handler_name", "payload", "expected"),
    [
        ("log-scan", "log_scan", {"run": "json-run"}, {"run": "json-run"}),
        (
            "compare-crawls",
            "compare_crawls",
            {"before": {"run": "before"}, "after": {"run": "after"}},
            {"before": {"run": "before"}, "after": {"run": "after"}},
        ),
    ],
)
def test_json_input_reaches_handlers_with_path_flags(
    monkeypatch, capsys, command, handler_name, payload, expected
):
    """#218: path flags are convenient overrides, not parser requirements for JSON input."""
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO(""))
    monkeypatch.setitem(handlers.HANDLERS, handler_name, lambda **kw: {"ok": True, "echo": kw})
    rc = cli.main([command, "--input", json.dumps(payload)])
    assert rc == 0
    echo = json.loads(capsys.readouterr().out)["echo"]
    assert echo == expected


@pytest.mark.parametrize(
    ("command", "handler_name", "payload", "flag_args", "fields"),
    [
        (
            "sitemap-crawl",
            "sitemap_crawl",
            {"concurrency": 3},
            ["--url", "https://example.com", "--concurrency", "0"],
            ("concurrency",),
        ),
        (
            "duplicate-check",
            "duplicate_check",
            {"threshold": 0.9},
            ["--threshold", "0"],
            ("threshold",),
        ),
        (
            "site-audit",
            "site_audit",
            {"limit": 25, "concurrency": 5},
            ["--url", "https://example.com", "--limit", "0", "--concurrency", "0"],
            ("limit", "concurrency"),
        ),
        (
            "regions-check",
            "regions_check",
            {"limit": 12},
            ["--url", "https://example.com", "--limit", "0"],
            ("limit",),
        ),
        (
            "backlinks-check",
            "backlinks_check",
            {"concurrency": 3},
            ["--target", "example.com", "--donors", "https://donor.example", "--concurrency", "0"],
            ("concurrency",),
        ),
        (
            "keywords-expand",
            "keywords_expand",
            {"limit": 300},
            ["--phrase", "floor heating", "--limit", "0"],
            ("limit",),
        ),
        (
            "keywords-exact",
            "keywords_exact",
            {"region": 225},
            ["--keywords", "floor heating", "--region", "0"],
            ("region",),
        ),
        (
            "serp-fetch",
            "serp_fetch",
            {"top": 10},
            ["--query", "floor heating", "--top", "0"],
            ("top",),
        ),
        (
            "google-keywords",
            "google_keywords",
            {"location_code": 2840, "limit": 100},
            ["--seed", "floor heating", "--location-code", "0", "--limit", "0"],
            ("location_code", "limit"),
        ),
        (
            "google-serp",
            "google_serp",
            {"location_code": 2840, "depth": 10},
            ["--query", "floor heating", "--location-code", "0", "--depth", "0"],
            ("location_code", "depth"),
        ),
    ],
)
def test_explicit_zero_numeric_flags_override_json(
    monkeypatch, capsys, command, handler_name, payload, flag_args, fields
):
    """#219: zero is an explicit value, never a signal to keep JSON/default input."""
    monkeypatch.setattr(cli.sys, "stdin", _NeverReadStdin())
    monkeypatch.setitem(handlers.HANDLERS, handler_name, lambda **kw: {"ok": True, "echo": kw})
    rc = cli.main([command, "--input", json.dumps(payload), *flag_args])
    assert rc == 0
    echo = json.loads(capsys.readouterr().out)["echo"]
    assert {field: echo[field] for field in fields} == {field: 0 for field in fields}


def test_path_flags_override_json_input(monkeypatch, capsys):
    """#218: direct flag forms remain supported when JSON carries a stale path."""
    monkeypatch.setattr(cli.sys, "stdin", _NeverReadStdin())
    monkeypatch.setitem(handlers.HANDLERS, "log_scan", lambda **kw: {"ok": True, "echo": kw})
    rc = cli.main(["log-scan", "--input", '{"run":"json-run"}', "--run", "flag-run"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["echo"]["run"] == "flag-run"


# Issue #156: these flags each identify a command's whole input just as --url does, but were
# missing from SOURCE_FLAGS, so a per-line loop over any one of them silently stopped after its
# first iteration (the exact failure the comment above SOURCE_FLAGS warns about).
FORMERLY_MISSING_SOURCE_FLAGS = [
    ("keywords-expand", ["--phrase", "floor heating"]),
    ("keywords-seasonality", ["--phrase", "floor heating"]),
    ("keywords-exact", ["--keywords", "floor heating"]),
    ("serp-fetch", ["--query", "floor heating"]),
    ("serp-fetch", ["--queries", "floor heating,floor screed"]),
    ("google-keywords", ["--keywords", "floor heating"]),
    ("google-keywords", ["--seed", "floor heating"]),
    ("google-serp", ["--query", "floor heating"]),
    ("metrika-setup", ["--counter", "12345678"]),
    ("metrika-report", ["--counter", "12345678"]),
    ("compare-crawls", ["--before", "before.json", "--after", "after.json"]),
]


@pytest.mark.parametrize("command,flag_args", FORMERLY_MISSING_SOURCE_FLAGS)
def test_formerly_missing_source_flags_are_recognized(command, flag_args):
    """``_has_source_flag`` must return True from the flag alone — derived from the parser
    (``_source_flag``), not from a hand-kept list that can silently omit a new flag again."""
    args = cli.build_parser().parse_args([command, *flag_args])
    assert cli._has_source_flag(args)


def test_a_loop_over_a_formerly_missing_flag_runs_every_line(monkeypatch, capsys):
    """Reproduces the exact bug report: ``while read p; do seohead keywords-expand --phrase
    "$p"; done < phrases.txt`` used to process only the first of three lines because
    ``--phrase`` was absent from SOURCE_FLAGS and the CLI blocked on/consumed stdin."""
    monkeypatch.setitem(handlers.HANDLERS, "keywords_expand", lambda **kw: {"ok": True, "echo": kw})
    phrases = ["floor heating", "underfloor heating", "floor screed"]
    seen = []
    for phrase in phrases:
        # A fresh guard per line stands in for the shared, still-open file descriptor a real
        # shell loop reads from: the CLI must not touch it once --phrase already supplies input.
        monkeypatch.setattr(cli.sys, "stdin", _NeverReadStdin("leftover\n" * 100))
        rc = cli.main(["keywords-expand", "--phrase", phrase])
        assert rc == 0
        seen.append(json.loads(capsys.readouterr().out)["echo"]["phrase"])
    assert seen == phrases
