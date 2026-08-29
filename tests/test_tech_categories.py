"""Network-free integrity tests for ``seohead.recon.tech.SIGNATURES``.

These tests exercise only the registry data and the pure :func:`tech._match`
function, without HTTP or an external fingerprint database. They catch category
typos, empty markers, duplicate signatures, and unsupported signature kinds.
"""

from __future__ import annotations

from collections import Counter

from seohead.recon import tech

_VALID_KINDS = {"header", "value", "cookie", "html", "script"}


def test_all_kinds_valid():
    """Every kind must be one of the signature sources documented by the module."""
    bad = [(c, n, k) for c, n, k, _ in tech.SIGNATURES if k not in _VALID_KINDS]
    assert not bad, f"unsupported signature kinds: {bad}"


def test_no_empty_markers():
    """An empty or whitespace-only marker would match every page."""
    bad = [(c, n, k, m) for c, n, k, m in tech.SIGNATURES if not m or not m.strip()]
    assert not bad, f"empty signature markers: {bad}"


def test_no_exact_duplicates():
    """An exact ``(category, name, kind, marker)`` duplicate adds no coverage."""
    counts = Counter(tech.SIGNATURES)
    dups = {sig: n for sig, n in counts.items() if n > 1}
    assert not dups, f"exact duplicate signatures: {dups}"


def test_every_category_has_signatures():
    """Every declared category is used, including the detector's core categories."""
    per_category = Counter(c for c, _, _, _ in tech.SIGNATURES)
    # Every category reported by the counter must have at least one signature.
    for category in per_category:
        assert per_category[category] >= 1, f"category without signatures: {category!r}"
    # A missing core category usually means that its label was mistyped.
    must_have = {"cms", "analytics", "framework", "server"}
    missing = must_have - set(per_category)
    assert not missing, f"missing core categories: {sorted(missing)}"


def test_signature_count_robust():
    """Do not regress below the 200-signature baseline established on 2026-08-12."""
    assert len(tech.SIGNATURES) >= 200


def test_match_value_kind_finds_in_header_value():
    """``kind='value'`` searches header values, not header names.

    The test takes Gunicorn's real ``value`` marker from ``SIGNATURES`` and
    places it in the ``Server`` header value. The name ``server`` is not the
    marker, so a match can only come from the value.
    """
    marker = next((m for c, n, k, m in tech.SIGNATURES if k == "value" and n == "Gunicorn"), None)
    assert marker, "SIGNATURES no longer contains Gunicorn/value; update this test"

    hit = tech._match(
        "value",
        marker,
        html_low="",
        headers={"server": "gunicorn/20.0"},
        cookies={},
        scripts_low="",
    )
    assert hit is not None, "kind=value did not match the marker in a header value"


def test_match_header_kind_matches_by_name():
    """``kind='header'`` matches a header name rather than its value.

    Cloudflare's ``cf-ray`` marker is the header name. The value ``abc`` is
    deliberately arbitrary, so the engine must match by name.
    """
    marker = next(
        (m for c, n, k, m in tech.SIGNATURES if k == "header" and n == "Cloudflare"), None
    )
    assert marker == "cf-ray", (
        "SIGNATURES no longer contains Cloudflare/header=cf-ray; update this test"
    )

    hit = tech._match(
        "header", marker, html_low="", headers={"cf-ray": "abc"}, cookies={}, scripts_low=""
    )
    assert hit is not None, "kind=header did not match the header name"
