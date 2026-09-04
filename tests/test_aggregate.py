"""Aggregate: issue fingerprinting is stable regardless of (capped) locations."""

from __future__ import annotations

from seohead.sf.core.aggregate import _fingerprint
from seohead.sf.core.models import Issue


def test_fingerprint_independent_of_locations():
    a = Issue(
        check="BROKEN_INTERNAL_LINK",
        severity="critical",
        source="s",
        message="m",
        target_url="https://x/p",
        status_code=404,
        locations=[{"source_url": "https://x/a"}],
    )
    b = Issue(
        check="BROKEN_INTERNAL_LINK",
        severity="critical",
        source="s",
        message="m",
        target_url="https://x/p",
        status_code=404,
        locations=[{"source_url": "https://x/a"}, {"source_url": "https://x/b"}],
    )
    assert _fingerprint(a) == _fingerprint(b)
