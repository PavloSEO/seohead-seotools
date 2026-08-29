# ruff: noqa: RUF001 -- Intentional Cyrillic fixtures verify Russian SEO extraction.
"""Network-independent tests for page fact extraction."""

from seohead.tools import page_facts

# This fixture intentionally remains in Russian to verify extraction from a
# localized product page, including visible text, breadcrumbs, and RUB prices.
HTML = """
<html lang="ru"><head>
  <title>Кроссовки Acme X — купить за 5990 ₽ | Магазин</title>
  <meta name="description" content="Кроссовки для бега">
  <link rel="canonical" href="https://shop.example.com/products/acme-x">
  <meta property="og:site_name" content="Acme Shop">
  <meta property="og:title" content="Кроссовки Acme X">
  <meta property="og:type" content="product">
  <meta property="article:published_time" content="2025-01-15T09:00:00Z">
</head><body>
  <nav class="breadcrumb"><a href="/">Главная</a> · <a href="/products">Товары</a></nav>
  <h1>Кроссовки Acme X</h1>
  <div itemscope itemtype="https://schema.org/Product">
    <span itemprop="name">Кроссовки Acme X</span>
    <span itemprop="price" content="5990">5990 ₽</span>
    <meta itemprop="priceCurrency" content="RUB">
    <div itemprop="aggregateRating" itemscope itemtype="https://schema.org/AggregateRating">
      <span itemprop="ratingValue">4.7</span>
      <span itemprop="reviewCount">42</span>
    </div>
  </div>
  <div itemscope itemtype="https://schema.org/Organization">
    <span itemprop="name">Acme Shop</span>
    <span itemprop="telephone">+7 800 123-45-67</span>
    <link itemprop="sameAs" href="https://t.me/acmeshop">
  </div>
  <footer>
    <a href="https://t.me/acmeshop">Telegram</a>
    <a href="https://vk.com/acmeshop">VK</a>
  </footer>
  <script type="application/ld+json">
  {"@context":"https://schema.org","@type":"Product","name":"Кроссовки Acme X",
   "offers":{"@type":"Offer","price":"5990","priceCurrency":"RUB"}}
  </script>
</body></html>
"""


def test_base_facts_from_parser():
    f = page_facts.extract(HTML, "https://shop.example.com/products/acme-x")
    assert f["title"] == "Кроссовки Acme X — купить за 5990 ₽ | Магазин"
    assert f["canonical"] == "https://shop.example.com/products/acme-x"
    assert f["og"]["og:site_name"] == "Acme Shop"
    assert f["og"]["og:type"] == "product"
    assert f["h1"] == "Кроссовки Acme X"


def test_published_time_from_meta():
    f = page_facts.extract(HTML, "https://shop.example.com/products/acme-x")
    assert f["published_time"] == "2025-01-15T09:00:00Z"


def test_existing_types_extracted_from_jsonld():
    f = page_facts.extract(HTML, "https://shop.example.com/products/acme-x")
    assert "Product" in f["existing_types"]
    assert "Offer" in f["existing_types"]


def test_price_from_microdata_is_fact_not_heuristic():
    f = page_facts.extract(HTML, "https://shop.example.com/products/acme-x")
    assert f["price"] is not None
    assert f["price"]["value"] == "5990"
    assert f["price"]["currency"] == "RUB"
    assert f["price"]["heuristic"] is False
    assert f["price"]["source"] == "microdata"


def test_rating_from_microdata():
    f = page_facts.extract(HTML, "https://shop.example.com/products/acme-x")
    assert f["rating"]["value"] == "4.7"
    assert f["rating"]["count"] == "42"
    assert f["rating"]["heuristic"] is False


def test_same_as_collects_social_links_and_itemprop():
    f = page_facts.extract(HTML, "https://shop.example.com/products/acme-x")
    same = set(f["same_as"])
    assert "https://t.me/acmeshop" in same
    assert "https://vk.com/acmeshop" in same


def test_organization_from_microdata():
    f = page_facts.extract(HTML, "https://shop.example.com/products/acme-x")
    org = f["organization"]
    assert org["name"] == "Acme Shop"
    assert org["telephone"] == "+7 800 123-45-67"


def test_breadcrumbs_from_nav_when_no_jsonld_breadcrumbs():
    f = page_facts.extract(HTML, "https://shop.example.com/products/acme-x")
    names = [b["name"] for b in f["breadcrumbs"]]
    assert "Главная" in names
    assert "Товары" in names
    assert all(b["url"].startswith("https://shop.example.com") for b in f["breadcrumbs"])


def test_price_heuristic_from_text_when_no_microdata():
    # Russian price copy is intentional: the heuristic must recognize RUB text.
    html = "<html><body><h1>X</h1><p>Цена: 1290 руб.</p></body></html>"
    f = page_facts.extract(html, "https://example.com/p")
    assert f["price"] is not None
    assert f["price"]["heuristic"] is True
    assert f["price"]["source"] == "text"


def test_missing_signals_return_none_not_fake_values():
    html = "<html><body><h1>Plain page</h1><p>Copy without a price or date.</p></body></html>"
    f = page_facts.extract(html, "https://example.com/about")
    assert f["price"] is None
    assert f["rating"] is None
    assert f["published_time"] is None
    assert f["organization"]["name"] is None
