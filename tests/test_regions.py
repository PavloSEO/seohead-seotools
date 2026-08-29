"""Offline regional-structure tests; only ``analyze_regions`` reaches the network."""

from __future__ import annotations

from collections import Counter

from seohead.recon.regions import (
    NON_REGION_HOSTS,
    REGION_SLUGS,
    _findings,
    _phones,
    _registrable,
    analyze_regions,
    classify_url,
    detect_region,
    discover_regional_links,
)

# ── Region dictionary ────────────────────────────────────────────────────────


def test_translit_variants_collapse_into_one_region():
    """Transliteration variants must resolve to one city, not competing regions."""
    # Russian city names are intentional localized output from the regional dictionary.
    for slug in ("msk", "moskva", "moscow"):
        assert detect_region(slug) == "Москва"
    for slug in ("spb", "piter", "sankt-peterburg"):
        assert detect_region(slug) == "Санкт-Петербург"


def test_region_is_found_inside_a_compound_token():
    """Detect a regional slug embedded in a compound satellite label."""
    # Russian city names are intentional localized output from the regional dictionary.
    assert detect_region("site-msk") == "Москва"
    assert detect_region("nasosy-spb") == "Санкт-Петербург"


def test_unknown_token_is_none_not_a_guess():
    assert detect_region("catalog") is None
    assert detect_region("") is None
    assert detect_region("xyz123") is None


def test_service_subdomains_are_not_regions():
    for host in ("www", "api", "cdn", "shop", "lk"):
        assert host in NON_REGION_HOSTS
        assert host not in REGION_SLUGS


# ── Registrable domain ───────────────────────────────────────────────────────


def test_registrable_domain_handles_compound_zones():
    # The .ru fixtures intentionally exercise Russian compound public suffix handling.
    assert _registrable("msk.site.ru") == "site.ru"
    assert _registrable("site.ru") == "site.ru"
    assert _registrable("shop.site.com.ru") == "site.com.ru"


# ── Structure classification ─────────────────────────────────────────────────


def test_subdomain_scheme():
    # Russian city names are intentional localized output from the regional dictionary.
    r = classify_url("https://msk.example.com/catalog", "example.com")
    assert (r["scheme"], r["region"]) == ("subdomain", "Москва")


def test_folder_scheme():
    # Russian city names are intentional localized output from the regional dictionary.
    r = classify_url("https://example.com/spb/services", "example.com")
    assert (r["scheme"], r["region"]) == ("folder", "Санкт-Петербург")


def test_separate_domain_is_a_satellite():
    # Russian city names are intentional localized output from the regional dictionary.
    r = classify_url("https://pumps-ekb.test/", "example.com")
    assert (r["scheme"], r["region"]) == ("domain", "Екатеринбург")


def test_www_and_ordinary_pages_are_the_main_site():
    assert classify_url("https://www.example.com/catalog/pumps", "example.com")["scheme"] == "main"
    assert classify_url("https://example.com/about", "example.com")["region"] is None


def test_common_first_segments_are_not_regions():
    """Common site sections such as /catalog/ and /blog/ are not regions."""
    for path in ("/catalog/x", "/blog/post", "/services/seo", "/ru/page"):
        assert classify_url(f"https://example.com{path}", "example.com")["region"] is None


# ── City switcher ────────────────────────────────────────────────────────────

# Russian city names and anchor labels intentionally test localized switcher detection.
SWITCHER = """<html><body>
  <a href="https://msk.example.com/">Москва</a>
  <a href="https://spb.example.com/">Санкт-Петербург</a>
  <a href="/ekb/">Екатеринбург</a>
  <a href="https://msk.example.com/">Москва</a>
  <a href="/catalog/pumps">Catalog</a>
  <a href="#top">Back to top</a>
  <a href="tel:+74951234567">Call</a>
</body></html>"""


def test_switcher_links_are_found_and_deduplicated():
    found = discover_regional_links(SWITCHER, "https://example.com/")
    regions = sorted(f["region"] for f in found)
    assert regions == ["Екатеринбург", "Москва", "Санкт-Петербург"]


def test_anchors_and_service_schemes_are_skipped():
    urls = [f["url"] for f in discover_regional_links(SWITCHER, "https://example.com/")]
    assert not any(u.startswith(("tel:", "#")) for u in urls)
    assert not any("catalog" in u for u in urls)


def test_region_from_anchor_text_is_marked_as_weaker_evidence():
    """A city in anchor text is evidence, but weaker than a regional URL."""
    # This Russian anchor intentionally verifies localized city-name recognition.
    html = '<html><body><a href="/branch-1/">Красноярск</a></body></html>'
    found = discover_regional_links(html, "https://example.com/")
    assert found and found[0]["region"] == "Красноярск"
    assert found[0]["from_anchor_text"] is True


# ── Telephone numbers ────────────────────────────────────────────────────────


def test_phones_are_normalised_to_ten_digits():
    html = 'Call <a href="tel:+7 (495) 123-45-67">+7 (495) 123-45-67</a> or 8 812 765 43 21'
    assert _phones(html) == ["4951234567", "8127654321"]


# ── Findings ─────────────────────────────────────────────────────────────────


def _page(url, region, scheme="subdomain", **kw):
    base = {
        "url": url,
        "ok": True,
        "status": 200,
        "final_url": url,
        "redirected": False,
        "title": f"Pumps — {region}",
        "h1": "Pumps",
        "canonical": "",
        "word_count": 300,
        "phones": ["4951234567"],
        "noindex": False,
        "html": "<p>" + " ".join(f"word{i}" for i in range(200)) + "</p>",
        "region": region,
        "scheme": scheme,
        "slug": "x",
    }
    base.update(kw)
    return base


MAIN = {"ok": True, "url": "https://example.com/", "final_url": "https://example.com/"}


def test_identical_content_across_regions_is_reported():
    # Russian city names intentionally model regional targeting in Yandex.
    pages = [
        _page("https://msk.example.com/", "Москва"),
        _page("https://spb.example.com/", "Санкт-Петербург"),
    ]
    out = _findings(MAIN, pages, Counter({"subdomain": 2}))
    assert any("Content matches" in f for f in out)


def test_canonical_to_another_host_is_flagged_as_self_removal():
    # Russian city names intentionally model regional targeting in Yandex.
    pages = [_page("https://msk.example.com/", "Москва", canonical="https://example.com/")]
    out = _findings(MAIN, pages, Counter({"subdomain": 1}))
    assert any("canonicalize to another host" in f for f in out)


def test_redirect_to_main_means_the_region_does_not_exist():
    # Russian city names intentionally model regional targeting in Yandex.
    pages = [
        _page(
            "https://msk.example.com/", "Москва", final_url="https://example.com/", redirected=True
        )
    ]
    out = _findings(MAIN, pages, Counter({"subdomain": 1}))
    assert any("redirect to the main site" in f for f in out)


def test_same_phone_everywhere_is_flagged():
    # Russian city names intentionally model regional targeting in Yandex.
    pages = [
        _page("https://msk.example.com/", "Москва"),
        _page("https://spb.example.com/", "Санкт-Петербург"),
    ]
    out = _findings(MAIN, pages, Counter({"subdomain": 2}))
    assert any("phone number is identical" in f for f in out)


def test_city_missing_from_title_is_flagged():
    # Russian city names intentionally model localized title checks.
    pages = [
        _page("https://msk.example.com/", "Москва", title="Pumps — buy"),
        _page("https://spb.example.com/", "Санкт-Петербург", title="Pumps — order"),
    ]
    out = _findings(MAIN, pages, Counter({"subdomain": 2}))
    assert any("city is missing from the title" in f for f in out)


def test_two_schemes_at_once_are_flagged():
    # Russian city names intentionally model regional targeting in Yandex.
    pages = [
        _page("https://msk.example.com/", "Москва"),
        _page("https://example.com/spb/", "Санкт-Петербург", scheme="folder"),
    ]
    out = _findings(MAIN, pages, Counter({"subdomain": 1, "folder": 1}))
    assert any("both subdomains and folders" in f for f in out)


def test_satellites_get_an_affiliate_warning():
    # Russian city names intentionally model regional satellite targeting in Yandex.
    pages = [
        _page("https://example-msk.test/", "Москва", scheme="domain"),
        _page("https://example-spb.test/", "Санкт-Петербург", scheme="domain"),
    ]
    out = _findings(MAIN, pages, Counter({"domain": 2}))
    assert any("affiliate site signals" in f for f in out)


def test_dead_regional_hosts_are_reported():
    # Russian city names intentionally model regional targeting in Yandex.
    pages = [
        _page("https://msk.example.com/", "Москва", ok=False, status=None, error="ConnectError")
    ]
    out = _findings(MAIN, pages, Counter({"subdomain": 1}))
    assert any("are unavailable or return errors" in f for f in out)


def test_clean_structure_says_so_instead_of_staying_silent():
    # Russian city names intentionally model regional targeting in Yandex.
    pages = [
        _page(
            "https://msk.example.com/",
            "Москва",
            phones=["4951234567"],
            html="<p>" + " ".join(f"moscow{i}" for i in range(200)) + "</p>",
        ),
        _page(
            "https://spb.example.com/",
            "Санкт-Петербург",
            phones=["8127654321"],
            html="<p>" + " ".join(f"petersburg{i}" for i in range(200)) + "</p>",
        ),
    ]
    out = _findings(MAIN, pages, Counter({"subdomain": 2}))
    assert out == ["Checked regions: 2; no major structural errors were found."]


def test_nothing_found_is_not_reported_as_everything_is_fine():
    """Zero checked pages is not a clean result; JS may render the city switcher."""
    out = _findings(MAIN, [], Counter())
    assert len(out) == 1
    assert "No regional URLs were found" in out[0]
    assert "rendered by JavaScript" in out[0]
    assert "no major structural errors" not in out[0]


# ── Input boundaries ─────────────────────────────────────────────────────────


def test_empty_url_is_data_not_a_crash():
    assert analyze_regions("")["ok"] is False
    assert analyze_regions("   ")["ok"] is False


def test_bad_limit_is_rejected_before_any_network_call():
    r = analyze_regions("https://example.com/", limit="many")
    assert r["ok"] is False and "limit" in r["error"]
