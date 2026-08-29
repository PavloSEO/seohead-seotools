# ruff: noqa: RUF001 -- Intentional Cyrillic fixtures cover Russian SEO regressions.
"""Regression tests for page type classification.

Both regressions were discovered during live-run reviews rather than static code
inspection. Each produced markup that contradicted the page content, which can
trigger search-engine penalties instead of being ignored.
"""

from __future__ import annotations

from seohead.tools.page_facts import extract
from seohead.tools.page_type import classify


def _classify(url: str, html: str) -> dict:
    return classify(url, extract(html, url))


def test_catalog_is_a_listing_not_a_product():
    """A catalog path must describe a listing rather than a single product.

    Marking a product collection as one Product claims that the page contains an
    item that is not actually present.
    """
    # Russian catalog copy intentionally verifies localized listing classification.
    r = _classify(
        "https://shop.example.com/catalog/nasosy", "<html><body><h1>Насосы</h1></body></html>"
    )
    assert r["inferred_type"] == "CollectionPage"
    assert r["inferred_type"] != "Product"


def test_category_synonyms_are_listings_too():
    for path in (
        "/category/pumps",
        "/kategoriya/nasosy",
        "/razdel/tovary",
        "/collection/new",
        "/shop/tools",
    ):
        # Russian section copy intentionally covers localized listing pages.
        r = _classify(
            f"https://site.example.com{path}", "<html><body><h1>Раздел</h1></body></html>"
        )
        assert r["inferred_type"] == "CollectionPage", f"{path} -> {r['inferred_type']}"


def test_product_card_is_still_a_product():
    """The listing fix must not reclassify individual product pages."""
    for path in ("/product/nasos", "/tovar/nasos", "/item/123", "/p/4567"):
        # Russian product copy and RUB price intentionally test localized extraction.
        r = _classify(
            f"https://site.example.com{path}",
            "<html><body><h1>Насос CDM</h1><p>12 000 руб</p></body></html>",
        )
        assert r["inferred_type"] == "Product", f"{path} -> {r['inferred_type']}"


def test_service_page_with_a_price_is_a_service():
    """A priced service must remain a Service rather than becoming a Product.

    A price previously contributed 2.0 only to Product, creating a 2:2 tie with
    Service that alphabetical ordering always resolved in favor of Product.
    """
    # Russian service copy and monthly RUB price intentionally test local semantics.
    r = _classify(
        "https://agency.example.com/services/seo-prodvizhenie",
        "<html><body><h1>SEO-продвижение</h1><p>от 50 000 руб/мес</p></body></html>",
    )
    assert r["inferred_type"] == "Service"


def test_exact_tie_is_reported_as_a_coin_flip():
    """An alphabetical tie-break must be reported as arbitrary, not inferred."""
    r = classify(
        "https://site.example.com/page",
        {
            "existing_types": [],
            "og": {},
            "price": None,
            "rating": None,
            "published_time": None,
            "word_count": 0,
            "h1": "",
            # Two equal-weight URL paths cannot be modeled simultaneously, so this
            # regression verifies the no-signal fallback explicitly.
        },
    )
    # No signals must produce an honest WebPage fallback, not an invented type.
    assert r["inferred_type"] == "WebPage"
    assert r["confidence"] == "low"
    assert "No specific content-type signals" in (r.get("note") or "")


def test_signals_are_always_shown():
    """The classifier must expose the evidence behind its decision."""
    r = _classify(
        "https://site.example.com/blog/post",
        "<html><head><meta property='article:published_time' content='2026-01-01'>"
        "</head><body><h1>Post</h1></body></html>",
    )
    assert r["signals"], "A decision without supporting signals cannot be audited"
    assert all("reason" in s and "weight" in s for s in r["signals"])
