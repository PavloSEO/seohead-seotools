"""Offline tests for Screaming Frog runner paths, empty exports, and throttling."""

import os
import struct

import pytest

from seohead.sf.core import runner
from seohead.sf.core import spiderconfig as SC

# ---------------------------------------------------------------- paths


def test_build_command_keeps_absolute_output(tmp_path):
    out = tmp_path / "exports"
    cmd = runner.build_command(
        "/bin/sf",
        source_arg="--crawl",
        source_value="https://example.com/",
        output_folder=str(out),
        config={},
    )
    i = cmd.index("--output-folder")
    assert os.path.isabs(cmd[i + 1])


def test_run_sf_normalizes_relative_output(tmp_path, monkeypatch):
    """Convert a relative output path to an absolute path before starting SF."""
    # This test exercises command construction, not DNS/SSRF enforcement.
    monkeypatch.setenv("SEOHEAD_ALLOW_PRIVATE_NETWORKS", "1")
    seen: dict = {}

    def fake_run(cmd, *args, **kwargs):
        i = cmd.index("--output-folder")
        seen["folder"] = cmd[i + 1]
        # Simulate a completed SF run by creating an export for run_sf to detect.
        os.makedirs(seen["folder"], exist_ok=True)
        with open(os.path.join(seen["folder"], "internal_all.csv"), "w") as fh:
            fh.write("Address\n")

        class P:
            returncode = 0
            stdout = ""
            stderr = ""

        return P()

    monkeypatch.setattr(runner, "resolve_cli", lambda *a, **k: "/bin/sf")
    monkeypatch.setattr(runner, "_run_watched", fake_run)
    monkeypatch.chdir(tmp_path)

    got = runner.run_sf(
        mode="crawl",
        source="https://example.com/",
        output_folder="rel/exports",
        config={},
        log=lambda m: None,
    )
    assert os.path.isabs(seen["folder"])
    assert seen["folder"] == str(tmp_path / "rel" / "exports")
    assert os.path.isabs(got)


def test_run_sf_empty_exports_is_loud(tmp_path, monkeypatch):
    """Raise a clear error when SF exits successfully without writing exports."""
    # Keep the test fully offline: URL policy is covered in test_public_safety.py.
    monkeypatch.setenv("SEOHEAD_ALLOW_PRIVATE_NETWORKS", "1")

    def fake_run(cmd, *args, **kwargs):
        class P:
            returncode = 0
            stdout = ""
            stderr = "FATAL - Directory does not exist: rel/exports"

        return P()

    monkeypatch.setattr(runner, "resolve_cli", lambda *a, **k: "/bin/sf")
    monkeypatch.setattr(runner, "_run_watched", fake_run)

    with pytest.raises(RuntimeError) as err:
        runner.run_sf(
            mode="crawl",
            source="https://example.com/",
            output_folder=str(tmp_path / "exports"),
            config={},
            log=lambda m: None,
        )
    msg = str(err.value)
    assert "no exports" in msg
    assert "FATAL" in msg  # The message includes the relevant tail of SF output.


def test_run_sf_rejects_a_stale_export_folder_from_a_prior_run(tmp_path, monkeypatch):
    """#215: a zero-exit run that writes nothing new must not fall back to an old export."""
    monkeypatch.setenv("SEOHEAD_ALLOW_PRIVATE_NETWORKS", "1")

    output = tmp_path / "exports"
    old = output / "previous-run"
    old.mkdir(parents=True)
    (old / "internal_all.csv").write_text("Address\nhttps://old.example/\n", encoding="utf-8")

    def fake_run(cmd, *args, **kwargs):
        class P:
            returncode = 0
            stdout = ""
            stderr = "FATAL - startup failed"

        return P()

    monkeypatch.setattr(runner, "resolve_cli", lambda *a, **k: "/bin/sf")
    monkeypatch.setattr(runner, "_run_watched", fake_run)

    with pytest.raises(RuntimeError) as err:
        runner.run_sf(
            mode="crawl-list",
            source=str(tmp_path / "urls.txt"),
            output_folder=str(output),
            config={},
            log=lambda m: None,
        )
    assert "no exports" in str(err.value)


def test_run_sf_accepts_a_genuinely_new_export_folder_beside_an_old_one(tmp_path, monkeypatch):
    """A real new run must still succeed even when a prior run's folder is still there."""
    monkeypatch.setenv("SEOHEAD_ALLOW_PRIVATE_NETWORKS", "1")

    output = tmp_path / "exports"
    old = output / "previous-run"
    old.mkdir(parents=True)
    (old / "internal_all.csv").write_text("Address\nhttps://old.example/\n", encoding="utf-8")

    def fake_run(cmd, *args, **kwargs):
        fresh = output / "2026-09-05"
        fresh.mkdir()
        (fresh / "internal_all.csv").write_text("Address\nhttps://new.example/\n", encoding="utf-8")

        class P:
            returncode = 0
            stdout = ""
            stderr = ""

        return P()

    monkeypatch.setattr(runner, "resolve_cli", lambda *a, **k: "/bin/sf")
    monkeypatch.setattr(runner, "_run_watched", fake_run)

    got = runner.run_sf(
        mode="crawl",
        source="https://example.com/",
        output_folder=str(output),
        config={},
        log=lambda m: None,
    )
    assert got == str(output / "2026-09-05")


def test_run_sf_accepts_only_the_in_memory_trusted_loopback_proxy(tmp_path, monkeypatch):
    proxy = "http://127.0.0.1:43123"

    def fake_run(cmd, *args, **kwargs):
        output = cmd[cmd.index("--output-folder") + 1]
        os.makedirs(output, exist_ok=True)
        with open(os.path.join(output, "internal_all.csv"), "w") as handle:
            handle.write("Address\n")

        class P:
            returncode = 0
            stdout = ""
            stderr = ""

        return P()

    monkeypatch.delenv("SEOHEAD_ALLOW_PRIVATE_NETWORKS", raising=False)
    monkeypatch.setattr(runner, "resolve_cli", lambda *a, **k: "/bin/sf")
    monkeypatch.setattr(runner, "_run_watched", fake_run)

    result = runner.run_sf(
        mode="crawl",
        source=f"{proxy}/protected",
        output_folder=str(tmp_path / "exports"),
        config={"sf_cli": {"_trusted_loopback_proxy": proxy}},
        log=lambda message: None,
    )
    assert os.path.isabs(result)

    with pytest.raises(ValueError, match="private"):
        runner.run_sf(
            mode="crawl",
            source="http://127.0.0.1:43124/protected",
            output_folder=str(tmp_path / "other"),
            config={"sf_cli": {"_trusted_loopback_proxy": proxy}},
            log=lambda message: None,
        )


# ------------------------------------------------- serialized configuration


def _synthetic_config(flag: int = 0, rate: float = 2.0, junk_prefix: bytes = b"") -> bytes:
    """Build a minimal blob containing a production-shaped SpiderPerformanceConfig block."""
    return (
        junk_prefix
        + b"sr\x00)"
        + SC.PERF_CLASS
        + b"\x00\x00\x00\x00\x00\x00\x00\x01\x02\x00\x02Z\x00\x11mLimitPerformanceD\x00\x15"
        + SC.PERF_FIELD
        + SC.FIELDS_END
        + bytes([flag])
        + struct.pack(">d", rate)
        + b"sr\x00&seo.tail"
    )


def test_patch_speed_sets_flag_and_rate():
    blob = _synthetic_config(flag=0, rate=99.0, junk_prefix=b"HDR")
    patched = SC.patch_speed(blob, 2.0)
    assert SC.read_speed(patched) == (True, 2.0)
    # At most nine bytes change; every other byte remains identical.
    assert len(patched) == len(blob)
    diff = [i for i, (a, b) in enumerate(zip(blob, patched, strict=True)) if a != b]
    assert len(diff) <= 9


def test_patch_speed_rejects_out_of_range():
    blob = _synthetic_config()
    with pytest.raises(ValueError):
        SC.patch_speed(blob, 0.0)
    with pytest.raises(ValueError):
        SC.patch_speed(blob, 5000)


def test_patch_speed_rejects_foreign_blob():
    with pytest.raises(ValueError):
        SC.patch_speed(b"definitely not a Screaming Frog config", 2.0)


def test_patch_speed_rejects_broken_flag_byte():
    blob = _synthetic_config(flag=7)  # A non-boolean flag indicates an incompatible layout.
    with pytest.raises(ValueError):
        SC.patch_speed(blob, 2.0)


def test_build_throttled_config_writes_file(tmp_path):
    base = tmp_path / "base.seospiderconfig"
    base.write_bytes(_synthetic_config(flag=0, rate=10.0))
    dest = tmp_path / "out" / "throttled.seospiderconfig"
    path = SC.build_throttled_config(str(dest), urls_per_second=2.5, base=str(base))
    assert os.path.isfile(path)
    with open(path, "rb") as fh:
        assert SC.read_speed(fh.read()) == (True, 2.5)


def test_build_throttled_config_without_base_is_loud(tmp_path, monkeypatch):
    monkeypatch.setattr(SC, "CRAWL_CONFIG_GLOBS", (str(tmp_path / "nope" / "*"),))
    with pytest.raises(RuntimeError) as err:
        SC.build_throttled_config(
            str(tmp_path / "t.seospiderconfig"), urls_per_second=2.0, base=None
        )
    message = str(err.value).lower()
    assert "base" in message
    assert "screaming frog" in message


def test_apply_rate_limit_injects_config(tmp_path, monkeypatch):
    base = tmp_path / "base.seospiderconfig"
    base.write_bytes(_synthetic_config())
    cfg = {"sf_cli": {"max_urls_per_second": 2.0, "seospiderconfig": str(base)}}
    out = runner._apply_rate_limit(cfg, str(tmp_path), lambda m: None)
    patched = out["sf_cli"]["seospiderconfig"]
    assert patched != str(base) and os.path.isfile(patched)
    with open(patched, "rb") as fh:
        assert SC.read_speed(fh.read()) == (True, 2.0)
    # The source configuration remains unchanged.
    assert SC.read_speed(base.read_bytes()) == (False, 2.0)


def test_apply_rate_limit_noop_without_request(tmp_path):
    cfg = {"sf_cli": {}}
    assert runner._apply_rate_limit(cfg, str(tmp_path), lambda m: None) is cfg
