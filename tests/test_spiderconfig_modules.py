"""Reading module switches out of a serialized Screaming Frog config.

Fixtures are built here rather than committed: a real config carries GA4, Search
Console, Ahrefs and Majestic credentials.
"""

import struct

import pytest

from seohead.sf.core import spiderconfig as sc

TC_OBJECT = b"\x73"
TC_CLASSDESC = b"\x72"
SUFFIX = b"\x78\x70"  # TC_ENDBLOCKDATA + TC_NULL superclass


def _utf(text: str) -> bytes:
    raw = text.encode("utf-8")
    return struct.pack(">H", len(raw)) + raw


def build_config(class_name: str, fields: list[tuple[str, str]], values: bytes) -> bytes:
    """Build a one-class serialized stream with the given primitive fields."""
    body = bytearray()
    body += TC_OBJECT + TC_CLASSDESC + _utf(class_name)
    body += b"\x00" * 8  # serialVersionUID
    body += b"\x02"  # SC_SERIALIZABLE
    body += struct.pack(">H", len(fields))
    for typecode, name in fields:
        body += typecode.encode() + _utf(name)
    body += SUFFIX + values
    return b"\xac\xed\x00\x05" + bytes(body)


DUPLICATE = "seo.spider.config.DuplicateConfig"
DUPLICATE_FIELDS = [
    ("Z", "mNearDuplicateChecking"),
    ("I", "mNearDuplicateThreshold"),
    ("Z", "mOnlyIndexableForDuplicates"),
]


def test_reads_a_boolean_that_is_on():
    blob = build_config(DUPLICATE, DUPLICATE_FIELDS, b"\x01" + struct.pack(">i", 90) + b"\x00")
    assert sc.read_boolean_field(blob, DUPLICATE, "mNearDuplicateChecking") is True


def test_reads_a_boolean_that_is_off():
    blob = build_config(DUPLICATE, DUPLICATE_FIELDS, b"\x00" + struct.pack(">i", 90) + b"\x01")
    assert sc.read_boolean_field(blob, DUPLICATE, "mNearDuplicateChecking") is False


def test_offset_skips_preceding_primitives_of_the_right_width():
    """The int between the two booleans must be stepped over, not misread."""
    blob = build_config(DUPLICATE, DUPLICATE_FIELDS, b"\x00" + struct.pack(">i", 90) + b"\x01")
    assert sc.read_boolean_field(blob, DUPLICATE, "mOnlyIndexableForDuplicates") is True


def test_absent_class_raises_rather_than_guessing():
    blob = build_config(DUPLICATE, DUPLICATE_FIELDS, b"\x00\x00\x00\x00\x5a\x00")
    with pytest.raises(ValueError, match="not present"):
        sc.read_boolean_field(blob, "seo.spider.config.NoSuchConfig", "mAnything")


def test_absent_field_raises_rather_than_guessing():
    blob = build_config(DUPLICATE, DUPLICATE_FIELDS, b"\x00\x00\x00\x00\x5a\x00")
    with pytest.raises(ValueError, match="no primitive field"):
        sc.read_boolean_field(blob, DUPLICATE, "mNotThere")


def test_non_boolean_byte_is_refused_instead_of_reported_as_a_value():
    blob = build_config(DUPLICATE, DUPLICATE_FIELDS, b"\x07" + struct.pack(">i", 90) + b"\x00")
    with pytest.raises(ValueError, match="expected 0 or 1"):
        sc.read_boolean_field(blob, DUPLICATE, "mNearDuplicateChecking")


def test_reading_an_int_field_as_boolean_is_refused():
    blob = build_config(DUPLICATE, DUPLICATE_FIELDS, b"\x01" + struct.pack(">i", 90) + b"\x00")
    with pytest.raises(ValueError, match="not a boolean"):
        sc.read_boolean_field(blob, DUPLICATE, "mNearDuplicateThreshold")


def test_truncated_stream_raises():
    blob = build_config(DUPLICATE, DUPLICATE_FIELDS, b"")
    with pytest.raises(ValueError):
        sc.read_boolean_field(blob, DUPLICATE, "mOnlyIndexableForDuplicates")


def test_unreadable_modules_are_unknown_not_off():
    """A config with none of the module classes must report None, never False."""
    flags = sc.read_module_flags(
        build_config(DUPLICATE, DUPLICATE_FIELDS, b"\x00\x00\x00\x00\x5a\x00")
    )
    assert flags["near_duplicates"] is False
    assert flags["spelling"] is None
    assert flags["structured_data_json_ld"] is None
    assert set(flags) == set(sc.MODULE_FLAG_FIELDS)


def test_read_module_flags_never_raises_on_garbage():
    assert set(sc.read_module_flags(b"not a serialized stream at all").values()) == {None}


def test_speed_reader_and_field_reader_agree():
    """Cross-check: the general parser must match the dedicated speed reader."""
    perf = "seo.spider.config.SpiderPerformanceConfig"
    fields = [("Z", "mLimitPerformance"), ("D", "mUrlRequestsPerSecond")]
    blob = build_config(perf, fields, b"\x01" + struct.pack(">d", 2.0))
    assert sc.read_speed(blob) == (True, 2.0)
    assert sc.read_boolean_field(blob, perf, "mLimitPerformance") is True


# ── preflight ────────────────────────────────────────────────────────────────


def test_preflight_names_the_checks_that_will_be_skipped(tmp_path, monkeypatch):
    from seohead.sf import cli

    config = tmp_path / "base.seospiderconfig"
    lang = "seo.spider.config.LanguageToolConfig"
    fields = [("Z", "mGrammarCheckEnabled"), ("Z", "mNeedsRerun"), ("Z", "mSpellCheckEnabled")]
    config.write_bytes(build_config(lang, fields, b"\x00\x00\x00"))

    lines = cli.preflight_warnings(str(config))
    joined = " ".join(lines)
    assert "SPELLING_ERRORS" in joined
    assert "GRAMMAR_ERRORS" in joined


def test_preflight_stays_silent_about_modules_that_are_on(tmp_path):
    from seohead.sf import cli

    config = tmp_path / "base.seospiderconfig"
    lang = "seo.spider.config.LanguageToolConfig"
    fields = [("Z", "mGrammarCheckEnabled"), ("Z", "mNeedsRerun"), ("Z", "mSpellCheckEnabled")]
    config.write_bytes(build_config(lang, fields, b"\x01\x00\x01"))

    joined = " ".join(cli.preflight_warnings(str(config)))
    assert "SPELLING_ERRORS" not in joined
    assert "GRAMMAR_ERRORS" not in joined


def test_preflight_says_so_when_no_base_config_exists(monkeypatch):
    from seohead.sf import cli
    from seohead.sf.core import spiderconfig

    monkeypatch.setattr(spiderconfig, "CRAWL_CONFIG_GLOBS", ())
    lines = cli.preflight_warnings(None)
    assert len(lines) == 1
    assert "no Screaming Frog base config found" in lines[0]


def test_preflight_reports_unknown_modules_as_silence_not_as_off(tmp_path):
    """An unreadable module must not produce a "will be skipped" claim."""
    from seohead.sf import cli

    config = tmp_path / "base.seospiderconfig"
    config.write_bytes(b"not a serialized stream")
    joined = " ".join(cli.preflight_warnings(str(config)))
    assert "SPELLING_ERRORS" not in joined
