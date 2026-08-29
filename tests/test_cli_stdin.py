"""Ensure explicit CLI source flags do not consume piped standard input.

The regression surfaced when
``while read u; do seohead parse --url "$u"; done < urls.txt`` consumed the
entire input file during the first iteration.
"""

import io
import json

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
