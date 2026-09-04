"""Two crawled URLs can share one normalised key (issue #95).

``norm_url`` folds a trailing slash away on purpose, so a canonical written without one still
matches the page that has it. That tolerance is correct. The defect was using a many-to-one
normalisation as a one-to-one index: a WordPress site that serves ``/x`` as a 301 to ``/x/``
has both in the crawl, and reading whichever record was inserted first reported 78 live pages
as canonicalising to a redirect when the canonical target answers 200.
"""

from __future__ import annotations

import csv

from seohead.sf.core.audit import run_audit

COLS = [
    "Address",
    "Content Type",
    "Status Code",
    "Status",
    "Indexability",
    "Title 1",
    "Meta Description 1",
    "H1-1",
    "Canonical Link Element 1",
    "Redirect URL",
    "Meta Robots 1",
    "Word Count",
]
TITLE = "A descriptive page title with sufficient length"
DESC = "A meta description deliberately longer than seventy characters to clear the threshold."


def _row(url, *, status=200, indexability="Indexable", canonical="", redirect="", robots="index"):
    return [
        url,
        "text/html",
        str(status),
        "OK" if status == 200 else "Moved Permanently",
        indexability,
        TITLE,
        DESC,
        "H",
        canonical,
        redirect,
        robots,
        "500",
    ]


def _fired(tmp_path, rows):
    d = tmp_path / "exports"
    d.mkdir()
    with open(d / "internal_all.csv", "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLS)
        writer.writerows(rows)
    res = run_audit(input_mode="parse-exports", exports_dir=str(d), log=lambda m: None)
    out: dict[str, set[str]] = {}
    for issue in res.issues:
        out.setdefault(issue.check, set()).add(issue.target_url)
    return out


# The live shape: the slashless form is what pages link to, and it 301s to the slashed one.
SLASHLESS = "https://blog.example.com/author/name"
SLASHED = "https://blog.example.com/author/name/"


def test_a_canonical_is_not_a_redirect_when_a_variant_under_the_same_key_answers_200(tmp_path):
    rows = [
        _row("https://blog.example.com/post", canonical=SLASHED),
        _row(SLASHLESS, status=301, indexability="Non-Indexable", redirect=SLASHED),
        _row(SLASHED),
    ]
    fired = _fired(tmp_path, rows)
    assert "https://blog.example.com/post" not in fired.get("CANONICAL_TO_REDIRECT", set())


def test_the_order_the_two_variants_appear_in_does_not_change_the_answer(tmp_path):
    """The 200 arriving second is the case that broke: setdefault kept the 301."""
    rows = [
        _row("https://blog.example.com/post", canonical=SLASHED),
        _row(SLASHED),
        _row(SLASHLESS, status=301, indexability="Non-Indexable", redirect=SLASHED),
    ]
    fired = _fired(tmp_path, rows)
    assert "https://blog.example.com/post" not in fired.get("CANONICAL_TO_REDIRECT", set())


def test_a_canonical_whose_only_crawled_variant_is_a_redirect_still_fires(tmp_path):
    rows = [
        _row("https://blog.example.com/post", canonical=SLASHLESS),
        _row(
            SLASHLESS,
            status=301,
            indexability="Non-Indexable",
            redirect="https://blog.example.com/elsewhere/",
        ),
    ]
    fired = _fired(tmp_path, rows)
    assert "https://blog.example.com/post" in fired.get("CANONICAL_TO_REDIRECT", set())


def test_canonical_non_indexable_reads_every_variant_too(tmp_path):
    """The 301 variant is Non-Indexable; the 200 one is not. The canonical is fine."""
    rows = [
        _row("https://blog.example.com/post", canonical=SLASHED),
        _row(SLASHLESS, status=301, indexability="Non-Indexable", redirect=SLASHED),
        _row(SLASHED),
    ]
    fired = _fired(tmp_path, rows)
    assert "https://blog.example.com/post" not in fired.get("CANONICAL_NON_INDEXABLE", set())


def test_canonical_non_indexable_still_fires_when_no_variant_is_indexable(tmp_path):
    rows = [
        _row("https://blog.example.com/post", canonical=SLASHED),
        _row(SLASHLESS, status=301, indexability="Non-Indexable", redirect=SLASHED),
        _row(SLASHED, indexability="Non-Indexable", robots="noindex"),
    ]
    fired = _fired(tmp_path, rows)
    assert "https://blog.example.com/post" in fired.get("CANONICAL_NON_INDEXABLE", set())


def test_a_canonical_chain_names_the_variant_that_answers(tmp_path):
    """The chain is rendered from the index too, so it must name the 200, not the 301."""
    rows = [
        _row("https://blog.example.com/post", canonical=SLASHED),
        _row(SLASHLESS, status=301, indexability="Non-Indexable", redirect=SLASHED),
        _row(SLASHED, canonical="https://blog.example.com/final/"),
        _row("https://blog.example.com/final/"),
    ]
    d = tmp_path / "exports"
    d.mkdir()
    with open(d / "internal_all.csv", "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLS)
        writer.writerows(rows)
    res = run_audit(input_mode="parse-exports", exports_dir=str(d), log=lambda m: None)
    chains = [i for i in res.issues if i.check == "CANONICAL_CHAIN"]
    assert chains, "the fixture is a two-hop canonical chain"
    assert SLASHLESS not in chains[0].details["chain"]
