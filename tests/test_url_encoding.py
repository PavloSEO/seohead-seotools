"""URL hygiene checks must read the path a URL denotes, not its wire form.

Exports carry the URL as crawled, so a non-Latin path arrives percent-encoded.
RFC 3986 prefers uppercase hex digits, so every such URL looked uppercase and
none looked non-ASCII — both verdicts inverted, on every page of a site whose
URLs are written in its own language.
"""

from __future__ import annotations

import csv

from seohead.sf.config import load_config
from seohead.sf.core.context import AuditContext
from seohead.sf.core.loader import load_exports
from seohead.sf.core.rules import check_url_and_perf

# The same Cyrillic path twice: as Screaming Frog writes it, and as written.
ENCODED_CYRILLIC = "https://example.com/%D0%BA%D0%B0%D1%82%D0%B0%D0%BB%D0%BE%D0%B3/"
LITERAL_CYRILLIC = "https://example.com/каталог/"


def _checks_for(tmp_path, *urls) -> dict[str, set[str]]:
    path = tmp_path / "internal_all.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Address", "Content Type", "Status Code", "Indexability"])
        for url in urls:
            writer.writerow([url, "text/html", "200", "Indexable"])
    ctx = AuditContext(load_exports(str(tmp_path)), load_config(None))
    check_url_and_perf(ctx)
    found: dict[str, set[str]] = {}
    for issue in ctx.issues:
        found.setdefault(issue.check, set()).add(issue.target_url)
    return found


def test_percent_encoding_is_not_uppercase(tmp_path):
    found = _checks_for(tmp_path, ENCODED_CYRILLIC)
    assert ENCODED_CYRILLIC not in found.get("URL_UPPERCASE", set())


def test_percent_encoded_non_ascii_is_reported(tmp_path):
    found = _checks_for(tmp_path, ENCODED_CYRILLIC)
    assert ENCODED_CYRILLIC in found.get("URL_NON_ASCII", set())


def test_encoded_and_literal_forms_agree(tmp_path):
    encoded = _checks_for(tmp_path, ENCODED_CYRILLIC)
    literal = _checks_for(tmp_path, LITERAL_CYRILLIC)
    assert set(encoded) == set(literal)


def test_real_uppercase_is_still_reported(tmp_path):
    url = "https://example.com/About-Us/"
    assert url in _checks_for(tmp_path, url).get("URL_UPPERCASE", set())


def test_uppercase_survives_encoding(tmp_path):
    # %41 is "A": the path denotes /About, whichever way it is written.
    url = "https://example.com/%41bout/"
    assert url in _checks_for(tmp_path, url).get("URL_UPPERCASE", set())


def test_lowercase_ascii_path_is_clean(tmp_path):
    url = "https://example.com/catalogue/chairs/"
    found = _checks_for(tmp_path, url)
    assert "URL_UPPERCASE" not in found
    assert "URL_NON_ASCII" not in found
