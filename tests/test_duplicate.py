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


def test_find_duplicates_reports_exact_pair_as_exact_not_near():
    # /page-a and /page-a-copy are byte-for-byte identical text: an exact
    # duplicate, not a "near" one, so it must not double-report as a cluster.
    items = [
        {"id": "/page-a", "text": TEXT_A},
        {"id": "/page-a-copy", "text": TEXT_A_COPY},
        {"id": "/page-b", "text": TEXT_B},
        {"id": "/contacts", "text": TEXT_C},
    ]
    r = D.find_duplicates(items)
    assert r["ok"] is True
    assert r["count"] == 4
    assert r["clusters"] == []
    assert len(r["exact_duplicates"]) == 1
    assert set(r["exact_duplicates"][0]["members"]) == {"/page-a", "/page-a-copy"}


def test_near_cluster_found_while_exact_pair_excluded_from_it():
    # A known near-duplicate cluster (similar wording, not identical) alongside
    # a known exact-duplicate pair: the near pass must find the former and
    # must not also list the latter as a cluster.
    common = "the quick brown fox jumps over the lazy dog every single morning near the office"
    near_1 = common + " during the alpha release cycle"
    near_2 = common + " during the beta release cycle"
    items = [
        {"id": "/near-1", "text": near_1},
        {"id": "/near-2", "text": near_2},
        {"id": "/exact-a", "text": TEXT_A},
        {"id": "/exact-b", "text": TEXT_A_COPY},
    ]
    r = D.find_duplicates(items, threshold=0.8)
    assert r["ok"] is True
    cluster_members = {frozenset(c["members"]) for c in r["clusters"]}
    assert frozenset({"/near-1", "/near-2"}) in cluster_members
    assert not any({"/exact-a", "/exact-b"} <= set(c["members"]) for c in r["clusters"])
    assert {"/exact-a", "/exact-b"} == set(r["exact_duplicates"][0]["members"])


def test_rerun_with_new_threshold_is_pure_and_needs_no_new_data():
    # A stored corpus can be re-run at a different threshold at zero request
    # cost because find_duplicates never performs I/O.
    items = [{"id": "1", "text": TEXT_A}, {"id": "2", "text": TEXT_B}]
    first = D.find_duplicates(items, threshold=0.5)
    second = D.find_duplicates(items, threshold=0.99)
    assert first == D.find_duplicates(items, threshold=0.5)  # deterministic
    assert second != first


def test_only_indexable_excludes_non_indexable_items_by_default():
    items = [
        {"id": "/canonical-target", "text": TEXT_A, "indexable": True},
        {"id": "/canonicalized-twin", "text": TEXT_A_COPY, "indexable": False},
    ]
    default = D.find_duplicates(items)
    assert default["count"] == 1
    assert default["excluded_non_indexable"] == 1
    assert default["exact_duplicates"] == []

    audit_canonicals = D.find_duplicates(items, only_indexable=False)
    assert audit_canonicals["count"] == 2
    assert audit_canonicals["excluded_non_indexable"] == 0
    assert set(audit_canonicals["exact_duplicates"][0]["members"]) == {
        "/canonical-target",
        "/canonicalized-twin",
    }


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
