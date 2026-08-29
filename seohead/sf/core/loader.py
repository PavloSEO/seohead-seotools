"""Discover and load Screaming Frog exports from a directory.

Works the same for mode A (the runner just wrote them) and mode B (the user
exported them by hand). Files are matched to logical export keys by filename
tokens, so any reasonable SF naming works, and reading is encoding-tolerant
(SF emits UTF-8-with-BOM or UTF-16, sometimes XLSX).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import pandas as pd

# Logical export key -> filename token matchers.
#   "all": every token must appear in the filename (AND)
#   "none": no token may appear (used to keep tab exports from matching their
#           bulk ``*_inlinks`` cousins)
EXPORT_MATCHERS: dict[str, dict[str, list[str]]] = {
    # Master table — required.
    "internal_all": {"all": ["internal"], "none": ["inlinks", "outlinks"]},
    # Response-code tabs (NOT the inlinks bulk exports).
    "resp_4xx": {"all": ["4xx"], "none": ["inlinks"]},
    "resp_5xx": {"all": ["5xx"], "none": ["inlinks"]},
    "resp_3xx": {"all": ["3xx"], "none": ["inlinks"]},
    "resp_no_response": {"all": ["no_response"], "none": ["inlinks"]},
    "resp_blocked": {"all": ["blocked"], "none": ["inlinks"]},
    # Inlinks bulk exports (the localization source).
    "inlinks_4xx": {"all": ["4xx", "inlinks"]},
    "inlinks_5xx": {"all": ["5xx", "inlinks"]},
    "inlinks_3xx": {"all": ["3xx", "inlinks"]},
    "all_inlinks": {"all": ["all_inlinks"]},
    # Sitemaps.
    "sitemap_in": {"all": ["urls_in_sitemap"], "none": ["not", "non"]},
    "sitemap_not_in": {"all": ["urls_not_in_sitemap"]},
    "sitemap_orphan": {"all": ["orphan"]},
    "sitemap_non_indexable": {"all": ["non", "indexable", "sitemap"]},
    "sitemap_redirects": {"all": ["redirect", "sitemap"]},
    "sitemap_non_200": {"all": ["non", "200", "sitemap"]},
    # Images / structured data / titles / etc. (consumed when present).
    "images_missing_alt": {"all": ["missing_alt"]},
    "images_over_kb": {"all": ["images", "kb"]},
    "images_missing_size": {"all": ["missing_size"]},
    "titles_duplicate": {"all": ["page_titles", "duplicate"]},
    "titles_multiple": {"all": ["page_titles", "multiple"]},
    # Native hreflang error report (Directives:Hreflang) — list of flagged URLs.
    # Exclude the link-level "all_hreflang" bulk export so it routes to its own key.
    "hreflang": {"all": ["hreflang"], "none": ["all_hreflang", "all-hreflang"]},
    # Bulk Export → Links → All Hreflang: one row per hreflang annotation
    # (Source → Destination + lang). Drives the hreflang-graph checks (§7).
    "all_hreflang": {"all": ["all", "hreflang"]},
    "desc_duplicate": {"all": ["description", "duplicate"]},
    "redirect_chains": {"all": ["redirect_chains"]},
    "crawl_overview": {"all": ["crawl_overview"]},
    # Native filter exports (activate matching checks when present; else skipped).
    "security_mixed": {"all": ["mixed_content"]},
    "security_hsts": {"all": ["hsts"]},
    "structured_data_missing": {"all": ["structured", "missing"]},
}

READ_ENCODINGS = ("utf-8-sig", "utf-16", "utf-8", "latin-1")


@dataclass
class LoadedExports:
    """All exports found in a directory, plus the bookkeeping reporters need."""

    frames: dict[str, pd.DataFrame] = field(default_factory=dict)
    files: dict[str, str] = field(default_factory=dict)  # key -> path
    found: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    def get(self, key: str) -> pd.DataFrame | None:
        return self.frames.get(key)

    def has(self, key: str) -> bool:
        return key in self.frames


def read_table(path: str) -> pd.DataFrame:
    """Read a CSV/XLSX export, trying encodings SF is known to emit."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(path)
    last_err: Exception | None = None
    for enc in READ_ENCODINGS:
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False)
        except (UnicodeDecodeError, UnicodeError) as err:
            last_err = err
        except pd.errors.ParserError as err:
            # Wrong encoding can masquerade as a parser error (UTF-16 read as UTF-8).
            last_err = err
    raise ValueError(f"Could not decode export {path!r}: {last_err}")


def _matches(filename: str, matcher: dict[str, list[str]]) -> bool:
    low = filename.lower()
    for token in matcher.get("all", []):
        if token.lower() not in low:
            return False
    for token in matcher.get("none", []):
        if token.lower() in low:
            return False
    return bool(matcher.get("all"))


def discover_exports(exports_dir: str) -> dict[str, str]:
    """Map each logical export key to the best matching file path in a dir."""
    if not os.path.isdir(exports_dir):
        raise NotADirectoryError(f"Exports directory not found: {exports_dir}")
    candidates = [
        name
        for name in sorted(os.listdir(exports_dir))
        if name.lower().endswith((".csv", ".xlsx", ".xls"))
    ]
    found: dict[str, str] = {}
    for key, matcher in EXPORT_MATCHERS.items():
        for name in candidates:
            if _matches(name, matcher):
                found[key] = os.path.join(exports_dir, name)
                break
    return found


def load_exports(exports_dir: str, required: tuple[str, ...] = ("internal_all",)) -> LoadedExports:
    """Discover and read every recognized export; report what's missing."""
    paths = discover_exports(exports_dir)
    result = LoadedExports()
    for key, path in paths.items():
        try:
            result.frames[key] = read_table(path)
            result.files[key] = path
            result.found.append(key)
        except Exception as err:
            result.missing.append(f"{key} (read error: {err})")
    for key in EXPORT_MATCHERS:
        if key not in result.frames and key not in (m.split(" ")[0] for m in result.missing):
            result.missing.append(key)
    for key in required:
        if key not in result.frames:
            raise FileNotFoundError(
                f"Required export {key!r} not found in {exports_dir!r}. "
                "Export at least Internal:All from Screaming Frog."
            )
    return result
