"""Native evidence collection.

This package fetches and parses; it never decides what is wrong. Checks,
severities, scores and reports stay entirely with :mod:`seohead.sf`, and the two
meet only at the ``LoadedExports`` contract. Nothing here may import
``seohead.sf``, ``seohead.servers`` or ``seohead.cli``.
"""

from seohead.crawl.collect import CrawlResult, PageRecord, collect_urls
from seohead.crawl.evidence import build_evidence

__all__ = ["CrawlResult", "PageRecord", "build_evidence", "collect_urls"]
