"""Loader: autodetection and encoding-safe reads."""

from __future__ import annotations

import os
import random

import pytest

from seohead.sf.core.loader import discover_exports, load_exports, read_table


def test_discovers_internal_and_inlinks(exports_dir):
    found = discover_exports(exports_dir)
    assert "internal_all" in found
    assert "inlinks_4xx" in found
    # the inlinks file must NOT be mistaken for the 4xx response-code tab
    assert "resp_4xx" not in found


def test_reads_utf8_bom_content(exports_dir):
    df = read_table(os.path.join(exports_dir, "internal_all.csv"))
    assert "Address" in df.columns
    assert any("Industrial Pump Store" in str(v) for v in df["Title 1"].tolist())


def test_required_export_enforced(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        load_exports(str(empty))


def test_load_reports_found_and_missing(exports_dir):
    loaded = load_exports(exports_dir)
    assert "internal_all" in loaded.found
    assert loaded.has("inlinks_4xx")
    assert "sitemap_in" in loaded.missing


def test_load_records_which_encoding_each_export_was_read_with(exports_dir):
    """#160: nothing recorded the winning codec, so mojibake had no signal to find."""
    loaded = load_exports(exports_dir)
    assert loaded.encodings["internal_all"] == "utf-8-sig"


def test_audit_run_metadata_surfaces_export_encodings(result):
    """The per-file codec reaches audit.json's ``run``, not just LoadedExports."""
    assert result.run["exports_encodings"]["internal_all"] == "utf-8-sig"


# A realistic-size, Cyrillic-heavy row set. charset_normalizer scores encodings
# by script/frequency consistency, and a couple of short rows carry too little
# signal for it to prefer cp1251 over a similarly-shaped codec (e.g. cp1250) --
# this is the same volume of text a real Screaming Frog export would carry.
_CP1251_ROWS = [
    ("https://example.by/", "Главная страница сайта", "Добро пожаловать на сайт компании"),
    (
        "https://example.by/o-nas",
        "О компании — история и миссия",  # noqa: RUF001 -- real Cyrillic, not a homoglyph typo
        "Узнайте больше о компании",  # noqa: RUF001
    ),
    ("https://example.by/uslugi", "Услуги и решения для бизнеса", "Список услуг для клиентов"),
    (
        "https://example.by/kontakty",
        "Контакты и обратная связь",
        "Свяжитесь с нами",  # noqa: RUF001 -- real Cyrillic, not a homoglyph typo
    ),
]


def _write_cp1251_export(path) -> None:
    rows = ["Address,Content Type,Status Code,Title 1,Meta Description 1"]
    rows += [f"{url},text/html,200,{title},{desc}" for url, title, desc in _CP1251_ROWS]
    path.write_bytes(("\r\n".join(rows) + "\r\n").encode("cp1251"))


def test_cp1251_export_decodes_to_the_real_cyrillic_title(tmp_path):
    """#160: latin-1 used to accept this file too, mojibake'd (`Ãëàâíàÿ...`)."""
    csv_path = tmp_path / "internal_all.csv"
    _write_cp1251_export(csv_path)
    df = read_table(str(csv_path))
    assert df.iloc[0]["Title 1"] == "Главная страница сайта"
    assert df.attrs["encoding"] == "cp1251"


def test_genuinely_undecodable_bytes_raise_rather_than_accepted_as_latin1(tmp_path):
    """latin-1 could never fail here either -- every byte 0x00-0xFF is legal to it."""
    csv_path = tmp_path / "garbage.csv"
    rng = random.Random(1234)
    csv_path.write_bytes(bytes(rng.randrange(0x80, 0x100) for _ in range(400)))
    with pytest.raises(ValueError, match="Could not decode export"):
        read_table(str(csv_path))
