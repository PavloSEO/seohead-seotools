"""Normalize: non-finite values must not crash or poison JSON."""

from __future__ import annotations

from seohead.sf.core.normalize import to_float, to_int


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
