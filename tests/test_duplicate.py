"""Offline tests for near-duplicate detection with SimHash and LSH."""

from seohead.tools import duplicate as D

TEXT_A = (
    "Search engine optimization is the process of improving the quality and "
    "quantity of website traffic from search engines. SEO targets unpaid traffic "
    "rather than direct traffic or paid traffic."
)
TEXT_A_COPY = (
    "Search engine optimization is the process of improving the quality and "
    "quantity of website traffic from search engines. SEO targets unpaid traffic "
    "rather than direct traffic or paid traffic."
)
TEXT_B = (
    "Today is an excellent day to prepare dinner with fresh vegetables and fish. "
    "The recipe is simple and quick enough even for a beginner cook."
)
TEXT_C = "Company contact information: telephone number and email address."


def test_simhash_identical_texts_match():
    assert D.simhash(TEXT_A) == D.simhash(TEXT_A_COPY)
    assert D.similarity(D.simhash(TEXT_A), D.simhash(TEXT_A_COPY)) == 1.0


def test_simhash_different_texts_differ():
    fp_a = D.simhash(TEXT_A)
    fp_b = D.simhash(TEXT_B)
    assert fp_a != fp_b
    assert D.similarity(fp_a, fp_b) < 0.92


def test_fnv1a_is_deterministic():
    assert D.fnv1a_64("hello") == D.fnv1a_64("hello")
    assert D.fnv1a_64("hello") != D.fnv1a_64("world")


def test_shingles_overlap():
    sh = D.shingles(["a", "b", "c", "d"], k=3)
    assert sh == [("a", "b", "c"), ("b", "c", "d")]


def test_find_duplicates_clusters_similar():
    items = [
        {"id": "/page-a", "text": TEXT_A},
        {"id": "/page-a-copy", "text": TEXT_A_COPY},
        {"id": "/page-b", "text": TEXT_B},
        {"id": "/contacts", "text": TEXT_C},
    ]
    r = D.find_duplicates(items)
    assert r["ok"] is True
    assert r["count"] == 4
    # One cluster contains A and its copy; B and the contact page remain unique.
    assert len(r["clusters"]) == 1
    cluster = r["clusters"][0]
    assert set(cluster["members"]) == {"/page-a", "/page-a-copy"}
    assert cluster["min_similarity"] == 1.0


def test_threshold_respected():
    # Two moderately similar texts share a prefix but have different endings.
    base = "SEO audit checks titles meta headings links images structured data."
    t1 = base + " Unique tail one about technical crawling and indexing."
    t2 = base + " Completely different ending about content marketing strategy."
    items = [{"id": "1", "text": t1}, {"id": "2", "text": t2}]
    # The loose threshold forms a cluster; the strict threshold does not.
    loose = D.find_duplicates(items, threshold=0.5)
    strict = D.find_duplicates(items, threshold=0.99)
    assert len(loose["clusters"]) >= 1
    assert len(strict["clusters"]) == 0


def test_empty_input_returns_empty():
    r = D.find_duplicates([])
    assert r["count"] == 0 and r["clusters"] == []


def test_lsh_finds_candidates_without_pairwise_all():
    # A is near B and B is near C, so transitivity should place all three together.
    common = "the quick brown fox jumps over the lazy dog every single morning"
    items = [
        {"id": "A", "text": common + " alpha version notes for release one"},
        {"id": "B", "text": common + " beta version notes for release two"},
        {"id": "C", "text": common + " gamma version notes for release three"},
    ]
    r = D.find_duplicates(items, threshold=0.7)
    assert len(r["clusters"]) >= 1
    members = set()
    for c in r["clusters"]:
        members |= set(c["members"])
    assert {"A", "B", "C"} <= members


def test_fingerprints_hidden_by_default():
    items = [{"id": "a", "text": TEXT_A}, {"id": "b", "text": TEXT_B}]
    out = D.find_duplicates(items)
    assert out["ok"] and "fingerprints" not in out
    assert out["count"] == 2


def test_fingerprints_on_request():
    items = [{"id": "a", "text": TEXT_A}, {"id": "b", "text": TEXT_B}]
    out = D.find_duplicates(items, with_fingerprints=True)
    assert set(out["fingerprints"]) == {"a", "b"}


def test_fingerprints_empty_input_respects_flag():
    assert "fingerprints" not in D.find_duplicates([])
    assert D.find_duplicates([], with_fingerprints=True)["fingerprints"] == {}
