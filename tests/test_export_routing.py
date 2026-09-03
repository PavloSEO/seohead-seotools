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
    "crawl_overview.csv": "crawl_overview",
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
}


@pytest.mark.parametrize(("filename", "expected"), sorted(EXPORTS.items(), key=lambda kv: kv[0]))
def test_export_routes_to_one_key(filename, expected):
    keys = [key for key, matcher in EXPORT_MATCHERS.items() if _matches(filename, matcher)]
    assert keys == ([expected] if expected else [])
