"""Issue #155: a handler's own-reported failure (``ok: false``) must reach the exit code.

Before this fix, every command whose handler caught a network/parse/provider failure and
returned ``{"ok": False, ...}`` instead of raising (the documented invariant in
``docs/ARCHITECTURE.md``) printed that JSON and exited 0 regardless — a pipeline gating on
``$?`` could not tell success from failure. ``log-scan``'s exit 2 for a self-contradicting run
is a separate, deliberately distinct signal and must keep working unchanged.
"""

from __future__ import annotations

import json

from seohead import cli
from seohead.servers import handlers


def test_ok_false_handler_result_exits_nonzero(monkeypatch, capsys):
    monkeypatch.setitem(
        handlers.HANDLERS, "robots_check", lambda **kw: {"ok": False, "error": "boom"}
    )
    rc = cli.main(["robots-check", "--url", "https://example.com"])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out == {"ok": False, "error": "boom"}


def test_ok_true_handler_result_still_exits_zero(monkeypatch, capsys):
    monkeypatch.setitem(handlers.HANDLERS, "robots_check", lambda **kw: {"ok": True})
    rc = cli.main(["robots-check", "--url", "https://example.com"])
    assert rc == 0


def test_a_handler_with_no_ok_field_exits_zero(monkeypatch, capsys):
    """Not every result carries ``ok`` (e.g. ``images_download``); absence is not failure."""
    monkeypatch.setitem(handlers.HANDLERS, "robots_check", lambda **kw: {"count": 0})
    rc = cli.main(["robots-check", "--url", "https://example.com"])
    assert rc == 0


def test_a_real_forced_failure_exits_nonzero(capsys):
    """The reported reproduction: an unresolvable URL forces the tool layer's own ``ok: false``
    path (no monkeypatching), and the CLI must surface that in the exit code, not just stdout."""
    rc = cli.main(["ai-bots-check", "--url", "not a url"])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False


def test_log_scan_missing_run_dir_exits_one_not_two(tmp_path, capsys):
    """log-scan's own ``ok: false`` (no run to scan) is an ordinary failure — exit 1 — distinct
    from anomaly_count>0, which alone earns exit 2 (see test_logscan.py for that gate)."""
    empty = tmp_path / "empty"
    empty.mkdir()
    rc = cli.main(["log-scan", "--run", str(empty)])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert out["anomaly_count"] == 0


def test_an_uncaught_exception_still_exits_one_with_stderr_message(monkeypatch, capsys):
    """The crash path (a bug, not a reported failure) is unchanged: nothing on stdout, a concise
    message on stderr, exit 1 — same code as an ``ok: false`` result, per docs/USAGE.md."""

    def _boom(**kw):
        raise RuntimeError("kaboom")

    monkeypatch.setitem(handlers.HANDLERS, "robots_check", _boom)
    rc = cli.main(["robots-check", "--url", "https://example.com"])
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "kaboom" in captured.err
