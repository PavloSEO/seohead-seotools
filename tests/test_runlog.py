"""The journal must record every call, leak no secrets, and never break a run."""

import json

import pytest

from seohead import runlog


@pytest.fixture(autouse=True)
def journal_path(tmp_path, monkeypatch):
    path = tmp_path / "runs.jsonl"
    monkeypatch.setenv("SEOHEAD_RUN_LOG", str(path))
    return path


def test_a_successful_call_is_recorded(journal_path):
    with runlog.journal("cli", "parse", {"url": "https://example.com/"}) as facts:
        facts["count"] = 3
    entry = runlog.read_entries()[0]
    assert entry["tool"] == "parse"
    assert entry["interface"] == "cli"
    assert entry["ok"] is True
    assert entry["count"] == 3
    assert entry["duration_s"] >= 0


def test_a_failing_call_is_recorded_and_the_error_still_propagates(journal_path):
    with pytest.raises(ValueError), runlog.journal("cli", "parse", {"url": "x"}):
        raise ValueError("boom")
    entry = runlog.read_entries()[0]
    assert entry["ok"] is False
    assert "boom" in entry["error"]


@pytest.mark.parametrize(
    "name", ["api_key", "token", "AUTH", "password", "client_secret", "credentials"]
)
def test_credentials_never_reach_the_journal(journal_path, name):
    """A journal that leaks a key is worse than no journal, and leaks silently."""
    with runlog.journal("cli", "serp", {name: "super-secret-value", "url": "https://e.com/"}):
        pass
    text = journal_path.read_text()
    assert "super-secret-value" not in text
    assert "[redacted]" in text


def test_long_values_are_shortened_not_dropped(journal_path):
    with runlog.journal("cli", "parse", {"html": "x" * 5000}):
        pass
    value = runlog.read_entries()[0]["arguments"]["html"]
    assert value.endswith("…")
    assert len(value) < 500


def test_long_lists_are_summarised(journal_path):
    with runlog.journal("cli", "parse", {"urls": [f"u{i}" for i in range(50)]}):
        pass
    value = runlog.read_entries()[0]["arguments"]["urls"]
    assert len(value) == 11
    assert "40 more" in value[-1]


def test_the_same_call_gets_the_same_fingerprint():
    first = runlog.fingerprint("parse", {"url": "https://e.com/", "depth": 2})
    again = runlog.fingerprint("parse", {"depth": 2, "url": "https://e.com/"})
    other = runlog.fingerprint("parse", {"url": "https://e.com/x", "depth": 2})
    assert first == again, "argument order must not change identity"
    assert first != other


def test_logging_can_be_switched_off(monkeypatch, tmp_path):
    monkeypatch.setenv("SEOHEAD_RUN_LOG", "off")
    assert runlog.log_path() is None
    with runlog.journal("cli", "parse", {"url": "x"}):
        pass
    assert runlog.read_entries() == []


def test_an_unwritable_journal_does_not_break_the_run(monkeypatch, tmp_path):
    """A degraded observation must never fail an audit."""
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    # The parent of the journal is a regular file, so creating it must fail.
    monkeypatch.setenv("SEOHEAD_RUN_LOG", str(blocker / "runs.jsonl"))
    with runlog.journal("cli", "parse", {"url": "x"}):
        pass  # must not raise
    assert runlog.read_entries() == []


def test_a_truncated_final_line_does_not_hide_earlier_entries(journal_path):
    with runlog.journal("cli", "first", {}):
        pass
    with open(journal_path, "a", encoding="utf-8") as handle:
        handle.write('{"broken": ')
    entries = runlog.read_entries()
    assert [e["tool"] for e in entries] == ["first"]


def test_every_handler_is_journalled():
    """Registry-level wrapping is what makes this impossible to forget."""
    from seohead.servers.handlers import HANDLERS

    for name, fn in HANDLERS.items():
        assert getattr(fn, "__wrapped__", None) is not None, f"{name} is not journalled"


def test_a_handler_call_writes_exactly_one_entry(journal_path):
    from seohead.servers.handlers import HANDLERS

    with pytest.raises(ValueError):
        HANDLERS["parse"]()  # missing required argument
    assert len(journal_path.read_text().strip().splitlines()) == 1


def test_the_tools_own_ok_is_kept_apart_from_the_calls_ok(journal_path):
    """ "The call did not raise" and "the tool found a usable result" differ."""
    with runlog.journal("cli", "t", {}) as facts:
        facts["result_ok"] = False
    entry = runlog.read_entries()[0]
    assert entry["ok"] is True
    assert entry["result_ok"] is False


def test_entries_are_newest_first_and_limited(journal_path):
    for n in range(5):
        with runlog.journal("cli", f"t{n}", {}):
            pass
    assert [e["tool"] for e in runlog.read_entries(limit=2)] == ["t4", "t3"]


def test_the_journal_is_valid_jsonl(journal_path):
    with runlog.journal("cli", "parse", {"url": "https://e.com/"}):
        pass
    for line in journal_path.read_text().splitlines():
        json.loads(line)
