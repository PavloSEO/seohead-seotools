"""The shared audit context passed to every check.

It builds the normalized :class:`Page` list from ``Internal:All`` and exposes
helpers that respect config: :meth:`enabled`, :meth:`severity`, :meth:`add` and
:meth:`skip`. Checks stay small because all the bookkeeping lives here.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .loader import LoadedExports
from .models import Group, Issue, Page, SkippedCheck
from .normalize import INTERNAL_FIELD_MAP, norm_url, records_from_df
from .registry import check_meta

_norm_url = norm_url


class AuditContext:
    def __init__(self, exports: LoadedExports, config: dict[str, Any]):
        self.exports = exports
        self.config = config
        self.thresholds: dict[str, Any] = config.get("thresholds", {})
        self.requirements: dict[str, Any] = config.get("requirements", {})
        self.issues: list[Issue] = []
        self.groups: list[Group] = []
        self.skipped: list[SkippedCheck] = []
        self._skipped_ids: set[str] = set()
        self._group_seq: int = 0

        self.internal_df: pd.DataFrame = exports.get("internal_all")
        self.pages: list[Page] = []
        self.page_by_url: dict[str, Page] = {}
        self.page_by_norm: dict[str, Page] = {}  # normalized-URL index
        self.redirect_map: dict[str, str] = {}
        self._html_pages: list[Page] | None = None
        self._indexable_html_pages: list[Page] | None = None
        self._build_pages()

    # -- page construction --------------------------------------------------
    def _build_pages(self) -> None:
        if self.internal_df is None:
            return
        for rec in records_from_df(self.internal_df, INTERNAL_FIELD_MAP):
            url = rec.get("url")
            if not url:
                continue
            if url in self.page_by_url:
                # Duplicate row for the same URL (e.g. merged exports) — keep the
                # first; otherwise self.pages and page_by_url would disagree.
                continue
            page = Page(
                url=url,
                status_code=rec.get("status_code"),
                status=rec.get("status"),
                content_type=rec.get("content_type"),
                indexability=rec.get("indexability"),
                indexability_status=rec.get("indexability_status"),
                metrics=self._metrics_from_record(rec),
            )
            page.metrics["_record"] = rec  # private: full record for checks
            self.pages.append(page)
            self.page_by_url[url] = page
            self.page_by_norm.setdefault(_norm_url(url), page)
            if rec.get("redirect_url"):
                self.redirect_map[url] = rec["redirect_url"]

    @staticmethod
    def _metrics_from_record(rec: dict[str, Any]) -> dict[str, Any]:
        """Return the public per-page metrics block; derived statistics are added later."""
        h1_count = 0
        if rec.get("h1"):
            h1_count += 1
        if rec.get("h1_2"):
            h1_count += 1
        h2_count = 0
        if rec.get("h2"):
            h2_count += 1
        if rec.get("h2_2"):
            h2_count += 1
        h1_list = [v for v in (rec.get("h1"), rec.get("h1_2")) if v]
        return {
            "title": rec.get("title"),
            "title_length": rec.get("title_length"),
            "title_px": rec.get("title_px"),
            "meta_description": rec.get("meta_description"),
            "desc_length": rec.get("desc_length"),
            "h1_count": h1_count,
            "h1": h1_list,
            "h2_count": h2_count,
            "word_count": rec.get("word_count"),
            "text_ratio": rec.get("text_ratio"),
            "size_bytes": rec.get("size_bytes"),
            "size_vs_median_ratio": None,
            "bytes_per_word": None,
            "dom_depth": None,
            "dom_nodes": None,
            "inlinks": rec.get("inlinks"),
            "unique_inlinks": rec.get("unique_inlinks"),
            "outlinks": rec.get("outlinks"),
            "external_outlinks": rec.get("external_outlinks"),
            "crawl_depth": rec.get("crawl_depth"),
            "response_time": rec.get("response_time"),
            "canonical": rec.get("canonical"),
            "meta_robots": rec.get("meta_robots"),
            "link_score": rec.get("link_score"),
            "is_in_sitemap": None,
            "sitemap_lastmod": None,
            # "static" unless the collector recorded a fuller fetch (#18). An
            # SF export never has this column, so it defaults the same way a
            # native crawl that never escalated would.
            "representation": rec.get("representation") or "static",
        }

    # -- config-aware helpers ----------------------------------------------
    def enabled(self, check_id: str) -> bool:
        cfg = self.config.get("checks", {}).get(check_id, {})
        return cfg.get("enabled", True)

    def severity(self, check_id: str) -> str:
        overrides = self.config.get("severity_overrides", {})
        if check_id in overrides:
            return overrides[check_id]
        cfg = self.config.get("checks", {}).get(check_id, {})
        if "severity" in cfg:
            return cfg["severity"]
        return check_meta(check_id)["severity"]

    def add(self, check_id: str, **kw: Any) -> Issue | None:
        """Create and record an Issue, filling defaults from the registry."""
        if not self.enabled(check_id):
            return None
        meta = check_meta(check_id)
        issue = Issue(
            check=check_id,
            severity=self.severity(check_id),
            source=kw.pop("source", meta["source"]),
            message=kw.pop("message", meta["message"]),
            fix_hint=kw.pop("fix_hint", meta.get("fix")),
            **kw,
        )
        self.issues.append(issue)
        return issue

    def add_group(self, check_id: str, value: str | None, urls: list[str]) -> Group:
        prefix = check_id.split("_")[0][:6].upper()
        self._group_seq += 1
        group = Group(
            group_id=f"GRP-{prefix}-{self._group_seq:04d}",
            check=check_id,
            value=value,
            urls=urls,
            count=len(urls),
        )
        self.groups.append(group)
        return group

    def skip_unsupported(self, available: set[str]) -> None:
        """Skip every check whose declared export frame is absent.

        Declaring the dependency once beats each check discovering its own
        absence, and it makes the gap countable instead of invisible.
        """
        from seohead.sf.core.registry import CHECK_REQUIRES, missing_requirements

        for check_id in CHECK_REQUIRES:
            gone = missing_requirements(check_id, available)
            if gone:
                self.skip(check_id, "missing export: " + ", ".join(gone))

    def skip(self, check_id: str, reason: str) -> None:
        if check_id in self._skipped_ids:
            return
        self._skipped_ids.add(check_id)
        self.skipped.append(SkippedCheck(id=check_id, reason=reason))

    # -- convenience views (cached; pages are built once and not mutated) ----
    def html_pages(self) -> list[Page]:
        if self._html_pages is None:
            self._html_pages = [p for p in self.pages if p.is_html]
        return self._html_pages

    def indexable_html_pages(self) -> list[Page]:
        if self._indexable_html_pages is None:
            self._indexable_html_pages = [p for p in self.html_pages() if p.is_indexable]
        return self._indexable_html_pages
