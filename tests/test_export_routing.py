"""Every export file must route to exactly one logical key.

The matchers are substring rules over filenames, so a new one can silently
capture a file that belongs to another key. When that happens the audit does
not fail — it reports the wrong file's rows under the other file's meaning,
which is how every URL with hreflang came to be reported as an hreflang error.
"""

from __future__ import annotations

import pytest

from seohead.sf.core.loader import EXPORT_MATCHERS, _matches

# Filenames as Screaming Frog writes them, mapped to the key each belongs to.
# None means the file is not consumed and must not be claimed by any key.
EXPORTS = {
    "internal_all.csv": "internal_all",
    "response_codes_client_error_(4xx).csv": "resp_4xx",
    "response_codes_server_error_(5xx).csv": "resp_5xx",
    "response_codes_redirection_(3xx).csv": "resp_3xx",
    "response_codes_no_response.csv": "resp_no_response",
    "response_codes_blocked_by_robots.txt.csv": "resp_blocked",
    "response_codes_client_error_(4xx)_inlinks.csv": "inlinks_4xx",
    "response_codes_server_error_(5xx)_inlinks.csv": "inlinks_5xx",
    "response_codes_redirection_(3xx)_inlinks.csv": "inlinks_3xx",
    "all_inlinks.csv": "all_inlinks",
    "urls_in_sitemap.csv": "sitemap_in",
    "urls_not_in_sitemap.csv": "sitemap_not_in",
    "orphan_urls.csv": "sitemap_orphan",
    "non_indexable_urls_in_sitemap.csv": "sitemap_non_indexable",
    "redirect_urls_in_sitemap.csv": "sitemap_redirects",
    "non_200_urls_in_sitemap.csv": "sitemap_non_200",
    "images_missing_alt_text.csv": "images_missing_alt",
    "images_over_100_kb.csv": "images_over_kb",
    "images_missing_size_attributes.csv": "images_missing_size",
    "page_titles_duplicate.csv": "titles_duplicate",
    "page_titles_multiple.csv": "titles_multiple",
    "meta_description_duplicate.csv": "desc_duplicate",
    "redirect_chains.csv": "redirect_chains",
    # Deliberately unregistered (#286): SF writes it as a two-column metadata
    # header followed by a five-column table in one CSV, a shape no consumer
    # here parses, and claiming the key only turned a correctly-written
    # export into a false "read error".
    "crawl_overview.csv": None,
    "security_mixed_content.csv": "security_mixed",
    "security_missing_hsts_header.csv": "security_hsts",
    "structured_data_missing.csv": "structured_data_missing",
    "all_hreflang.csv": "all_hreflang",
    "all-hreflang.csv": "all_hreflang",
    "hreflang_missing_return_links.csv": "hreflang",
    "hreflang_non_200_hreflang_urls.csv": "hreflang",
    "hreflang_incorrect_language_and_region_codes.csv": "hreflang",
    # Listings, not problems: routing these to "hreflang" reports every
    # annotated URL as an error.
    "hreflang_all.csv": None,
    "hreflang_contains_hreflang.csv": None,
    "all_outlinks.csv": None,
    # A per-type Internal tab (Internal:HTML, Internal:Images, ...) is missing
    # every row of the other types, so it must never satisfy the required
    # Internal:All master table (#209).
    "internal_html.csv": None,
    "internal-all.csv": "internal_all",
}


@pytest.mark.parametrize(("filename", "expected"), sorted(EXPORTS.items(), key=lambda kv: kv[0]))
def test_export_routes_to_one_key(filename, expected):
    keys = [key for key, matcher in EXPORT_MATCHERS.items() if _matches(filename, matcher)]
    assert keys == ([expected] if expected else [])


# Screaming Frog's own report shape: a two-column metadata header, a blank
# line, then a five-column table -- the reason pandas' single read_csv call
# rejects it and the runner used to record a correctly-written export as a
# read error (#286).
_CRAWL_OVERVIEW_CSV = (
    '"Site Crawled","https://example.test/"\n'
    '"Date","2026-01-01"\n'
    '"Time","00:00:00"\n'
    '""\n'
    '"Summary","URLs","% of Total","Total URLs","Total URLs Description"\n'
    '"Total URLs Encountered","3","100,00%","3","URLs Encountered"\n'
)


def test_crawl_overview_is_not_registered():
    """#286: nothing here consumes crawl_overview, so it must not be a matcher key.

    Registering an export key that is never read commits to a shape no writer
    validates; a manually supplied Crawl Overview file must be left alone
    rather than misreported as broken.
    """
    assert "crawl_overview" not in EXPORT_MATCHERS


def test_crawl_overview_is_not_requested_by_default():
    """#286: the runner must not ask Screaming Frog to write a report nothing reads."""
    from seohead.sf.config import DEFAULT_CONFIG, LITE_EXPORTS

    assert "Crawl Overview" not in DEFAULT_CONFIG["exports"]["reports"]
    assert "Crawl Overview" not in LITE_EXPORTS["reports"]


def test_crawl_overview_export_is_never_flagged_as_a_read_error(tmp_path):
    """#286: a written-but-unregistered Crawl Overview must not surface as a read error.

    Placing the file next to a real ``Internal:All`` export reproduces a normal
    Mode A run: before the fix, ``load_exports`` still discovered and tried to
    parse ``crawl_overview.csv`` and recorded the resulting ``ValueError`` as
    ``"crawl_overview (read error: ...)"`` even though Screaming Frog wrote the
    file correctly.
    """
    from seohead.sf.core.loader import load_exports

    (tmp_path / "crawl_overview.csv").write_text(_CRAWL_OVERVIEW_CSV, encoding="utf-8-sig")
    (tmp_path / "internal_all.csv").write_text("Address,Status Code\n", encoding="utf-8-sig")

    result = load_exports(str(tmp_path))

    assert not any("crawl_overview" in entry for entry in result.missing)
    assert "crawl_overview" not in result.frames
