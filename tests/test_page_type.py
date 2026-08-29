"""Network-independent tests for page type classification."""

from seohead.tools import page_type


def test_existing_jsonld_product_is_high_confidence():
    facts = {
        "existing_types": ["Product", "Offer"],
        "og": {},
        "price": None,
        "rating": None,
        "published_time": None,
        "word_count": 0,
        "h1": None,
    }
    r = page_type.classify("https://shop.example.com/products/acme-x", facts)
    assert r["inferred_type"] == "Product"
    assert r["confidence"] == "high"
    assert any(s["reason"].startswith("Already declared") for s in r["signals"])


def test_article_signals_from_og_path_and_date():
    facts = {
        "existing_types": [],
        "og": {"og:type": "article"},
        "price": None,
        "rating": None,
        "published_time": "2025-01-15",
        "word_count": 1200,
        "h1": "Heading",
    }
    r = page_type.classify("https://site.example.com/blog/how-to-seo", facts)
    assert r["inferred_type"] == "Article"
    assert r["confidence"] in ("mid", "high")


def test_service_by_path_and_h1():
    # The Russian H1 intentionally verifies localized service-term classification.
    facts = {
        "existing_types": [],
        "og": {},
        "price": None,
        "rating": None,
        "published_time": None,
        "word_count": 200,
        "h1": "Услуги по SEO",
    }
    r = page_type.classify("https://agency.example.com/services/seo", facts)
    assert r["inferred_type"] == "Service"
    assert r["confidence"] in ("mid", "low")


def test_cyrillic_path_patterns_recognized():
    # The Russian contact heading intentionally exercises localized classification.
    facts = {
        "existing_types": [],
        "og": {},
        "price": None,
        "rating": None,
        "published_time": None,
        "word_count": 0,
        "h1": "Контакты",
    }
    r = page_type.classify("https://ru.example.com/kontakty", facts)
    assert r["inferred_type"] == "LocalBusiness"


def test_price_signal_pushes_to_product():
    facts = {
        "existing_types": [],
        "og": {},
        "price": {"value": "5990", "heuristic": True},
        "rating": None,
        "published_time": None,
        "word_count": 0,
        "h1": "X",
    }
    r = page_type.classify("https://shop.example.com/x", facts)
    assert r["inferred_type"] == "Product"


def test_no_signals_returns_webpage_low():
    facts = {
        "existing_types": [],
        "og": {},
        "price": None,
        "rating": None,
        "published_time": None,
        "word_count": 0,
        "h1": "About us",
    }
    r = page_type.classify("https://site.example.com/", facts)
    assert r["inferred_type"] == "WebPage"
    assert r["confidence"] == "low"
    assert "note" in r


def test_close_candidates_yield_note():
    # Price (Product) + /services/ path (Service) + rating (both) creates a close race.
    facts = {
        "existing_types": [],
        "og": {},
        "price": {"value": "100", "heuristic": False},
        "rating": {"value": "4.5"},
        "published_time": None,
        "word_count": 0,
        "h1": "Consultation",
    }
    r = page_type.classify("https://agency.example.com/services/cons", facts)
    assert r["inferred_type"] in ("Product", "Service")
    # The result must expose the ambiguity through either a note or alternatives.
    assert r.get("note") or r["alternatives"]


def test_signals_are_sorted_by_weight_desc():
    facts = {
        "existing_types": ["Product"],
        "og": {"og:type": "product"},
        "price": {"value": "5"},
        "rating": None,
        "published_time": None,
        "word_count": 0,
        "h1": None,
    }
    r = page_type.classify("https://shop.example.com/product/x", facts)
    weights = [s["weight"] for s in r["signals"]]
    assert weights == sorted(weights, reverse=True)
