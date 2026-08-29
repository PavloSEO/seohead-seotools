"""Value coercion and case-insensitive column mapping for SF exports.

Screaming Frog column headers and the module set in an export drift between
versions and configuration profiles. Everything here is tolerant: a
missing column yields ``None``, never an exception.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

import pandas as pd

# Canonical field -> ordered list of possible SF headers (matched case-insensitively).
# First match wins. Confirmed against a real SF 19.4 ``Internal:All`` export.
INTERNAL_FIELD_MAP: dict[str, list[str]] = {
    "url": ["Address", "URL"],
    "content_type": ["Content Type"],
    "status_code": ["Status Code"],
    "status": ["Status"],
    "indexability": ["Indexability"],
    "indexability_status": ["Indexability Status"],
    "title": ["Title 1", "Title"],
    "title_length": ["Title 1 Length"],
    "title_px": ["Title 1 Pixel Width"],
    "meta_description": ["Meta Description 1", "Meta Description"],
    "desc_length": ["Meta Description 1 Length"],
    "desc_px": ["Meta Description 1 Pixel Width"],
    "meta_keywords": ["Meta Keywords 1", "Meta Keywords"],
    "h1": ["H1-1"],
    "h1_length": ["H1-1 Length"],
    "h1_2": ["H1-2"],
    "h2": ["H2-1"],
    "h2_2": ["H2-2"],
    "meta_robots": ["Meta Robots 1"],
    "x_robots": ["X-Robots-Tag 1"],
    "canonical": ["Canonical Link Element 1", "Canonical Link Element"],
    "canonical_2": ["Canonical Link Element 2"],
    "meta_refresh": ["Meta Refresh 1"],
    "amphtml": ["amphtml Link Element", "AMP HTML"],
    "rel_next": ['rel="next" 1', "rel=next 1"],
    "rel_prev": ['rel="prev" 1', "rel=prev 1"],
    "size_bytes": ["Size (bytes)", "Size (Bytes)", "Size"],
    "transferred_bytes": ["Transferred (bytes)", "Transferred (Bytes)"],
    "word_count": ["Word Count"],
    "sentence_count": ["Sentence Count"],
    "avg_words_per_sentence": ["Average Words Per Sentence"],
    "flesch": ["Flesch Reading Ease Score"],
    "readability": ["Readability"],
    "http_version": ["HTTP Version"],
    "cookies": ["Cookies"],
    "text_ratio": ["Text Ratio"],
    "crawl_depth": ["Crawl Depth"],
    "folder_depth": ["Folder Depth"],
    "link_score": ["Link Score"],
    "inlinks": ["Inlinks"],
    "unique_inlinks": ["Unique Inlinks"],
    "outlinks": ["Outlinks"],
    "unique_outlinks": ["Unique Outlinks"],
    "external_outlinks": ["External Outlinks"],
    "closest_similarity": ["Closest Similarity Match"],
    "near_duplicates": ["No. Near Duplicates"],
    "hash": ["Hash", "Page Hash"],
    "response_time": ["Response Time"],
    "last_modified": ["Last Modified"],
    "redirect_url": ["Redirect URL", "Redirect URI"],
    "redirect_type": ["Redirect Type"],
    "hreflang": ["Hreflang"],
    "structured_data": ["Structured Data"],
    "validation_errors": ["Validation Errors"],
    "og_title": ["OG:Title"],
    "og_description": ["OG:Description"],
    "og_image": ["OG:Image", "OG:Image URL"],
    "og_url": ["OG:URL"],
    "spelling_errors": ["Spelling Errors"],
    "grammar_errors": ["Grammar Errors"],
}

# Canonical field -> headers for a ``*:Inlinks`` bulk export.
INLINKS_FIELD_MAP: dict[str, list[str]] = {
    "type": ["Type"],
    "source_url": ["Source", "From"],
    "destination_url": ["Destination", "To"],
    "anchor": ["Anchor Text", "Anchor"],
    "alt_text": ["Alt Text"],
    "status_code": ["Status Code"],
    "status": ["Status"],
    "follow": ["Follow"],
    "rel": ["Rel"],
    "target": ["Target"],
    "link_position": ["Link Position"],
    "link_path": ["Link Path"],
    "link_origin": ["Link Origin"],
}

# Canonical field -> headers for the Bulk Export → Links → ``All Hreflang``
# report. Each row is one hreflang annotation (source page → target URL + lang).
# Column names vary by SF version/profile, so multiple candidates are tried.
HREFLANG_FIELD_MAP: dict[str, list[str]] = {
    "source_url": ["Source", "From", "Address"],
    "destination_url": ["Destination", "To", "Hreflang URL", "Hreflang Target URL"],
    "hreflang": ["Hreflang", "Hreflang Language", "Language", "Lang"],
}


def normalize_value(value: Any) -> Any:
    """Empty strings / NaN -> ``None``; strip strings; pass numbers through."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else None
    return value


def to_int(value: Any) -> int | None:
    value = normalize_value(value)
    if value is None:
        return None
    try:
        f = float(value)
    except (ValueError, TypeError):
        return None
    if not math.isfinite(f):  # inf/-inf/nan would crash int() or poison JSON
        return None
    return int(f)


def to_float(value: Any) -> float | None:
    value = normalize_value(value)
    if value is None:
        return None
    try:
        f = float(value)
    except (ValueError, TypeError):
        return None
    # non-finite values are not valid JSON numbers — drop them
    return f if math.isfinite(f) else None


def is_true(value: Any) -> bool:
    value = normalize_value(value)
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"true", "yes", "1", "y"}


# Fields coerced to numbers. Everything else is a stripped string or None.
INT_FIELDS = frozenset(
    {
        "status_code",
        "title_length",
        "title_px",
        "desc_length",
        "desc_px",
        "h1_length",
        "size_bytes",
        "transferred_bytes",
        "word_count",
        "sentence_count",
        "crawl_depth",
        "folder_depth",
        "inlinks",
        "unique_inlinks",
        "outlinks",
        "unique_outlinks",
        "external_outlinks",
        "near_duplicates",
        "validation_errors",
        "spelling_errors",
        "grammar_errors",
    }
)
FLOAT_FIELDS = frozenset(
    {
        "text_ratio",
        "link_score",
        "response_time",
        "closest_similarity",
        "flesch",
        "avg_words_per_sentence",
    }
)


def norm_url(url: str | None) -> str:
    """Normalize a URL for equality/index lookups (strip, drop trailing /, lower)."""
    return (url or "").strip().rstrip("/").lower()


def find_column(df: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    """Return the actual column name matching any candidate, case-insensitively."""
    lower_map = {str(col).lower(): col for col in df.columns}
    for candidate in candidates:
        hit = lower_map.get(candidate.lower())
        if hit is not None:
            return hit
    return None


def resolve_columns(
    columns: Iterable[str], field_map: dict[str, list[str]]
) -> dict[str, str | None]:
    """Map each canonical field to its actual source column (once per frame)."""
    lower = {str(c).lower(): c for c in columns}
    resolved: dict[str, str | None] = {}
    for field_name, candidates in field_map.items():
        resolved[field_name] = next(
            (lower[c.lower()] for c in candidates if c.lower() in lower), None
        )
    return resolved


def records_from_df(df: pd.DataFrame, field_map: dict[str, list[str]]) -> list[dict[str, Any]]:
    """Vectorized projection of a frame onto canonical records.

    Resolves columns once, coerces numerics with ``pd.to_numeric`` in bulk and
    materializes plain Python dicts — ~orders of magnitude faster than calling
    :func:`row_to_record` under ``iterrows`` on large exports, and JSON-safe
    (no numpy scalars, no non-finite floats).
    """
    resolved = resolve_columns(df.columns, field_map)
    n = len(df)
    data: dict[str, Any] = {}
    for field_name, src in resolved.items():
        data[field_name] = df[src] if src is not None else pd.Series([None] * n, index=df.index)
    sub = pd.DataFrame(data, index=df.index)

    for field_name in INT_FIELDS | FLOAT_FIELDS:
        if field_name in sub.columns:
            sub[field_name] = pd.to_numeric(sub[field_name], errors="coerce")

    records: list[dict[str, Any]] = sub.to_dict("records")
    for rec in records:
        for field_name, value in rec.items():
            if value is None:
                continue
            if hasattr(value, "item"):  # numpy scalar -> Python scalar
                value = value.item()
                rec[field_name] = value
            if isinstance(value, float):
                if not math.isfinite(value):  # NaN/inf (incl. blanks) -> None
                    rec[field_name] = None
                elif field_name in INT_FIELDS:
                    rec[field_name] = int(value)
            elif isinstance(value, str):
                stripped = value.strip()
                rec[field_name] = stripped if stripped else None
    return records


def row_to_record(row: pd.Series, field_map: dict[str, list[str]]) -> dict[str, Any]:
    """Single-row projection (kept for ad-hoc use; bulk path is records_from_df)."""
    resolved = resolve_columns(row.index, field_map)
    record: dict[str, Any] = {}
    for field_name, col in resolved.items():
        raw = row[col] if col is not None else None
        if field_name in INT_FIELDS:
            record[field_name] = to_int(raw)
        elif field_name in FLOAT_FIELDS:
            record[field_name] = to_float(raw)
        else:
            record[field_name] = normalize_value(raw)
    return record
