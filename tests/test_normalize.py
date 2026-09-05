"""Normalize: non-finite values must not crash or poison JSON."""

from __future__ import annotations

from seohead.sf.core.normalize import norm_url, to_float, to_int


def test_to_int_handles_non_finite():
    assert to_int("inf") is None
    assert to_int(float("inf")) is None
    assert to_int("nan") is None
    assert to_int("-inf") is None
    assert to_int("42") == 42


def test_to_float_drops_non_finite():
    assert to_float("inf") is None
    assert to_float(float("nan")) is None
    assert to_float("3.5") == 3.5


# --------------------------------------------------------------------------
# #202 — norm_url must fold scheme/host but keep path/query/fragment case.
# --------------------------------------------------------------------------
def test_norm_url_keeps_path_case_distinct():
    assert norm_url("https://example.test/en") != norm_url("https://example.test/EN")
    assert norm_url("https://example.com/News") != norm_url("https://example.com/news")


def test_norm_url_still_folds_scheme_and_host_case():
    assert norm_url("HTTPS://Example.COM/x") == norm_url("https://example.com/x")


def test_norm_url_still_folds_a_trailing_slash():
    assert norm_url("https://example.com/x/") == norm_url("https://example.com/x")
    assert norm_url("https://example.com/") == norm_url("https://example.com")


def test_norm_url_query_case_is_preserved():
    assert norm_url("https://example.com/x?Q=A") != norm_url("https://example.com/x?q=a")
