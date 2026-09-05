"""Coverage for max-extraction checks: firing on native SF exports and skipping cleanly
without them (URL_TRACKING_PARAMS, OG_MISSING, GENERIC_ANCHOR_TEXT, CANONICAL_CHAIN,
CANONICAL_TO_REDIRECT, HREFLANG_BROKEN_TARGET, and related registry checks)."""

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
    "Canonical Link Element 2",
    "Meta Robots 1",
    "Meta Refresh 1",
    "HTTP Version",
    "Readability",
    "Flesch Reading Ease Score",
    "Average Words Per Sentence",
    "Outlinks",
    "External Outlinks",
    "Word Count",
]
TITLE = "A descriptive page title with sufficient length"
DESC = "A meta description deliberately longer than seventy characters to clear the validation threshold."


def _run(tmp_path, rows):
    d = tmp_path / "exports"
    d.mkdir()
    with open(d / "internal_all.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        w.writerows(rows)
    return run_audit(input_mode="parse-exports", exports_dir=str(d), log=lambda m: None)


def _fired(res):
    out = {}
    for i in res.issues:
        out.setdefault(i.check, set()).add(i.target_url)
    return out


def test_extended_checks_fire(tmp_path):
    rows = [
        # underscore URL, two canonicals, noarchive, http/1.1, very difficult,
        # long sentences, no internal outlinks (Outlinks is the internal count,
        # so zero means none; the five external links are counted separately)
        [
            "https://example.com/page_one",
            "text/html",
            "200",
            "OK",
            "Indexable",
            TITLE,
            DESC,
            "Primary heading",
            "https://example.com/page_one",
            "https://example.com/dup",
            "index,follow,noarchive",
            "",
            "1.1",
            "Very Difficult",
            "18",
            "30",
            "0",
            "5",
            "500",
        ],
        # clean URL, http/2, easy, high outlinks + high external
        [
            "https://example.com/page-two",
            "text/html",
            "200",
            "OK",
            "Indexable",
            TITLE,
            DESC,
            "Secondary heading",
            "https://example.com/page-two",
            "",
            "index,follow",
            "",
            "2",
            "Easy",
            "70",
            "12",
            "400",
            "150",
            "500",
        ],
    ]
    f = _fired(_run(tmp_path, rows))
    one, two = "https://example.com/page_one", "https://example.com/page-two"
    assert one in f.get("URL_UNDERSCORES", set())
    assert one in f.get("CANONICAL_MULTIPLE", set())
    assert one in f.get("NOARCHIVE", set())
    assert one in f.get("HTTP1_ONLY", set()) and two not in f.get("HTTP1_ONLY", set())
    assert one in f.get("READABILITY_DIFFICULT", set())
    assert one in f.get("LONG_SENTENCES", set())
    assert one in f.get("NO_INTERNAL_OUTLINKS", set())
    assert two in f.get("HIGH_OUTLINKS", set())
    assert two in f.get("HIGH_EXTERNAL_OUTLINKS", set())


def test_notranslate_unavailable_after_and_canonical_fragment_fire(tmp_path):
    """Issue #30: three of the cheap CONFIRMED gaps (directives + canonical)."""
    rows = [
        [
            "https://example.com/notranslate",
            "text/html",
            "200",
            "OK",
            "Indexable",
            TITLE,
            DESC,
            "H",
            "https://example.com/notranslate",
            "",
            "index,follow,notranslate",
            "",
            "2",
            "Easy",
            "70",
            "12",
            "10",
            "5",
            "500",
        ],
        [
            "https://example.com/unavailable",
            "text/html",
            "200",
            "OK",
            "Indexable",
            TITLE,
            DESC,
            "H",
            "https://example.com/unavailable",
            "",
            "index,follow,unavailable_after: 2099-01-01T00:00:00Z",
            "",
            "2",
            "Easy",
            "70",
            "12",
            "10",
            "5",
            "500",
        ],
        [
            "https://example.com/fragment",
            "text/html",
            "200",
            "OK",
            "Indexable",
            TITLE,
            DESC,
            "H",
            "https://example.com/fragment#section",
            "",
            "index,follow",
            "",
            "2",
            "Easy",
            "70",
            "12",
            "10",
            "5",
            "500",
        ],
        [
            "https://example.com/clean",
            "text/html",
            "200",
            "OK",
            "Indexable",
            TITLE,
            DESC,
            "H",
            "https://example.com/clean",
            "",
            "index,follow",
            "",
            "2",
            "Easy",
            "70",
            "12",
            "10",
            "5",
            "500",
        ],
    ]
    res = _run(tmp_path, rows)
    f = _fired(res)
    clean = "https://example.com/clean"
    assert f.get("NOTRANSLATE", set()) == {"https://example.com/notranslate"}
    unavail = next(i for i in res.issues if i.check == "UNAVAILABLE_AFTER")
    assert unavail.target_url == "https://example.com/unavailable"
    assert "2099" in unavail.details["directive"]
    assert f.get("CANONICAL_FRAGMENT", set()) == {"https://example.com/fragment"}
    assert clean not in f.get("NOTRANSLATE", set())
    assert clean not in f.get("UNAVAILABLE_AFTER", set())
    assert clean not in f.get("CANONICAL_FRAGMENT", set())


def test_native_export_checks_skip_without_export(tmp_path):
    rows = [
        [
            "https://example.com/",
            "text/html",
            "200",
            "OK",
            "Indexable",
            TITLE,
            DESC,
            "H",
            "https://example.com/",
            "",
            "index,follow",
            "",
            "2",
            "Easy",
            "70",
            "12",
            "20",
            "3",
            "500",
        ]
    ]
    res = _run(tmp_path, rows)
    skipped = {s.id for s in res.skipped}
    # registered native-filter checks honestly skip when their export is absent
    for cid in (
        "MIXED_CONTENT",
        "MISSING_HSTS",
        "STRUCTURED_DATA_MISSING",
        "IMG_OVER_KB",
        "IMG_MISSING_DIMENSIONS",
    ):
        assert cid in skipped


# --- Mode B cheap wins: URL_TRACKING_PARAMS, OG_MISSING, GENERIC_ANCHOR_TEXT ---


def test_url_tracking_params_fires(tmp_path):
    rows = [
        # utm_source + gclid on an indexable page -> fire
        [
            "https://example.com/landing?utm_source=newsletter&gclid=abc",
            "text/html",
            "200",
            "OK",
            "Indexable",
            TITLE,
            DESC,
            "H",
            "https://example.com/landing",
            "",
            "index,follow",
            "",
            "2",
            "Easy",
            "70",
            "12",
            "20",
            "3",
            "500",
        ],
        # clean URL -> must not fire
        [
            "https://example.com/clean",
            "text/html",
            "200",
            "OK",
            "Indexable",
            TITLE,
            DESC,
            "H",
            "https://example.com/clean",
            "",
            "index,follow",
            "",
            "2",
            "Easy",
            "70",
            "12",
            "20",
            "3",
            "500",
        ],
    ]
    f = _fired(_run(tmp_path, rows))
    assert "https://example.com/landing?utm_source=newsletter&gclid=abc" in f.get(
        "URL_TRACKING_PARAMS", set()
    )
    assert "https://example.com/clean" not in f.get("URL_TRACKING_PARAMS", set())


def test_url_tracking_params_skips_non_indexable(tmp_path):
    # a 4xx/non-indexable URL with tracking params must NOT fire (won't be indexed)
    rows = [
        [
            "https://example.com/gone?utm_source=x",
            "text/html",
            "404",
            "Not Found",
            "Non-Indexable",
            "Client Error",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ],
    ]
    f = _fired(_run(tmp_path, rows))
    assert "URL_TRACKING_PARAMS" not in f


_OG_COLS = [
    "Address",
    "Content Type",
    "Status Code",
    "Status",
    "Indexability",
    "Title 1",
    "Meta Description 1",
    "H1-1",
    "Canonical Link Element 1",
    "Meta Robots 1",
    "OG:Title",
    "OG:Image",
    "OG:URL",
]


def _run_og(tmp_path, rows):
    d = tmp_path / "exports"
    d.mkdir()
    with open(d / "internal_all.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(_OG_COLS)
        w.writerows(rows)
    return run_audit(input_mode="parse-exports", exports_dir=str(d), log=lambda m: None)


def test_og_missing_fires_and_skips(tmp_path):
    rows = [
        # page with OG -> OK, no issue
        [
            "https://example.com/with-og",
            "text/html",
            "200",
            "OK",
            "Indexable",
            TITLE,
            DESC,
            "H",
            "https://example.com/with-og",
            "index,follow",
            "OG Title",
            "https://img/x.jpg",
            "https://example.com/with-og",
        ],
        # indexable page missing og:title -> fire
        [
            "https://example.com/no-og",
            "text/html",
            "200",
            "OK",
            "Indexable",
            TITLE,
            DESC,
            "H",
            "https://example.com/no-og",
            "index,follow",
            "",
            "",
            "",
        ],
    ]
    res = _run_og(tmp_path, rows)
    fired = {}
    for i in res.issues:
        fired.setdefault(i.check, set()).add(i.target_url)
    assert "https://example.com/no-og" in fired.get("OG_MISSING", set())
    assert "https://example.com/with-og" not in fired.get("OG_MISSING", set())
    # details lists which core tags are absent
    og_issue = next(i for i in res.issues if i.check == "OG_MISSING")
    assert "og:title" in og_issue.details["missing_tags"]

    # skip case: export without any OG columns -> honest skip, no per-page noise
    rows_no_og = [
        [
            "https://example.com/a",
            "text/html",
            "200",
            "OK",
            "Indexable",
            TITLE,
            DESC,
            "H",
            "https://example.com/a",
            "index,follow",
        ]
    ]
    d2 = tmp_path / "no_og"
    d2.mkdir()
    de = d2 / "exports"
    de.mkdir()
    with open(de / "internal_all.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([c for c in _OG_COLS if not c.startswith("OG:")])
        w.writerow(rows_no_og[0])
    res2 = run_audit(input_mode="parse-exports", exports_dir=str(de), log=lambda m: None)
    assert "OG_MISSING" in {s.id for s in res2.skipped}
    assert "OG_MISSING" not in {i.check for i in res2.issues}


_INLINKS_COLS = [
    "Type",
    "Source",
    "Destination",
    "Anchor Text",
    "Alt Text",
    "Status Code",
    "Follow",
    "Target",
    "Rel",
    "Link Position",
    "Link Path",
]


def test_generic_anchor_text_fires_and_skips(tmp_path):
    d = tmp_path / "exports"
    d.mkdir()
    with open(d / "internal_all.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "Address",
                "Content Type",
                "Status Code",
                "Status",
                "Indexability",
                "Title 1",
                "Meta Description 1",
                "H1-1",
                "Canonical Link Element 1",
                "Meta Robots 1",
            ]
        )
        for u in (
            "https://example.com/",
            "https://example.com/page-a",
            "https://example.com/page-b",
        ):
            w.writerow(
                [u, "text/html", "200", "OK", "Indexable", TITLE, DESC, "H", u, "index,follow"]
            )
    with open(d / "all_inlinks.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(_INLINKS_COLS)
        # Cyrillic fixtures intentionally verify multilingual generic-anchor detection.
        w.writerow(
            [
                "Hyperlink",
                "https://example.com/page-a",
                "https://example.com/",
                "читать далее",
                "",
                "200",
                "true",
                "",
                "",
                "Content",
                "/html/body/a",
            ]
        )
        w.writerow(
            [
                "Hyperlink",
                "https://example.com/page-a",
                "https://example.com/",
                "тут",
                "",
                "200",
                "true",
                "",
                "",
                "Footer",
                "/html/body/footer/a",
            ]
        )
        w.writerow(
            [
                "Hyperlink",
                "https://example.com/page-b",
                "https://example.com/",
                "click here",
                "",
                "200",
                "true",
                "",
                "",
                "Content",
                "/html/body/a",
            ]
        )
        # This Cyrillic descriptive anchor must remain clean in a multilingual crawl.
        w.writerow(
            [
                "Hyperlink",
                "https://example.com/",
                "https://example.com/page-a",
                "Купить насос",
                "",
                "200",
                "true",
                "",
                "",
                "Content",
                "/html/body/a",
            ]
        )

    res = run_audit(input_mode="parse-exports", exports_dir=str(d), log=lambda m: None)
    fired = {}
    for i in res.issues:
        fired.setdefault(i.check, set()).add(i.target_url)
    # both source pages with generic anchors flagged; descriptive-only page is clean
    assert "https://example.com/page-a" in fired.get("GENERIC_ANCHOR_TEXT", set())
    assert "https://example.com/page-b" in fired.get("GENERIC_ANCHOR_TEXT", set())
    assert "https://example.com/" not in fired.get("GENERIC_ANCHOR_TEXT", set())
    # two generic links on page-a -> occurrences_count == 2
    pa_issue = next(
        i
        for i in res.issues
        if i.check == "GENERIC_ANCHOR_TEXT" and i.target_url == "https://example.com/page-a"
    )
    assert pa_issue.occurrences_count == 2
    anchors = {g["anchor"] for g in pa_issue.details["generic_links"]}
    # Expected Cyrillic values confirm that the report preserves localized anchors.
    assert anchors == {"читать далее", "тут"}

    # skip case: no inlinks export at all
    d2 = tmp_path / "no_inlinks"
    d2.mkdir()
    with open(d2 / "internal_all.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "Address",
                "Content Type",
                "Status Code",
                "Status",
                "Indexability",
                "Title 1",
                "Meta Description 1",
                "H1-1",
                "Canonical Link Element 1",
                "Meta Robots 1",
            ]
        )
        w.writerow(
            [
                "https://example.com/",
                "text/html",
                "200",
                "OK",
                "Indexable",
                TITLE,
                DESC,
                "H",
                "https://example.com/",
                "index,follow",
            ]
        )
    res2 = run_audit(input_mode="parse-exports", exports_dir=str(d2), log=lambda m: None)
    assert "GENERIC_ANCHOR_TEXT" in {s.id for s in res2.skipped}
    assert "GENERIC_ANCHOR_TEXT" not in {i.check for i in res2.issues}


# --- Mode B cheap wins: CANONICAL_CHAIN, CANONICAL_TO_REDIRECT, HREFLANG_BROKEN_TARGET ---


def test_canonical_chain_fires_and_skips(tmp_path):
    # A→B→C: B re-canonicalizes to C -> fire on A; B→C terminal, no fire on B/C.
    rows = [
        [
            "https://example.com/a",
            "text/html",
            "200",
            "OK",
            "Indexable",
            TITLE,
            DESC,
            "H",
            "https://example.com/b",
            "",
            "index,follow",
            "",
            "2",
            "Easy",
            "70",
            "12",
            "5",
            "1",
            "500",
        ],
        [
            "https://example.com/b",
            "text/html",
            "200",
            "OK",
            "Indexable",
            TITLE,
            DESC,
            "H",
            "https://example.com/c",
            "",
            "index,follow",
            "",
            "2",
            "Easy",
            "70",
            "12",
            "5",
            "1",
            "500",
        ],
        [
            "https://example.com/c",
            "text/html",
            "200",
            "OK",
            "Indexable",
            TITLE,
            DESC,
            "H",
            "https://example.com/c",
            "",
            "index,follow",
            "",
            "2",
            "Easy",
            "70",
            "12",
            "5",
            "1",
            "500",
        ],
    ]
    res = _run(tmp_path, rows)
    fired = {}
    for i in res.issues:
        fired.setdefault(i.check, set()).add(i.target_url)
    assert "https://example.com/a" in fired.get("CANONICAL_CHAIN", set())
    assert "https://example.com/b" not in fired.get("CANONICAL_CHAIN", set())
    assert "https://example.com/c" not in fired.get("CANONICAL_CHAIN", set())
    chain_issue = next(i for i in res.issues if i.check == "CANONICAL_CHAIN")
    assert chain_issue.details["chain"] == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    ]
    assert chain_issue.details["depth"] == 2
    assert chain_issue.details["loop"] is False

    # loop case: X→Y→X — both flagged, loop=True
    d2 = tmp_path / "loop"
    d2.mkdir()
    with open(d2 / "internal_all.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(COLS)
        for u, canon in (
            ("https://example.com/x", "https://example.com/y"),
            ("https://example.com/y", "https://example.com/x"),
        ):
            w.writerow(
                [
                    u,
                    "text/html",
                    "200",
                    "OK",
                    "Indexable",
                    TITLE,
                    DESC,
                    "H",
                    canon,
                    "",
                    "index,follow",
                    "",
                    "2",
                    "Easy",
                    "70",
                    "12",
                    "5",
                    "1",
                    "500",
                ]
            )
    res2 = run_audit(input_mode="parse-exports", exports_dir=str(d2), log=lambda m: None)
    fired2 = {}
    for i in res2.issues:
        fired2.setdefault(i.check, set()).add(i.target_url)
    assert "https://example.com/x" in fired2.get("CANONICAL_CHAIN", set())
    assert "https://example.com/y" in fired2.get("CANONICAL_CHAIN", set())
    loop_issue = next(
        i
        for i in res2.issues
        if i.check == "CANONICAL_CHAIN" and i.target_url == "https://example.com/x"
    )
    assert loop_issue.details["loop"] is True

    # skip case: no canonical column data at all
    d3 = tmp_path / "nocanon"
    d3.mkdir()
    with open(d3 / "internal_all.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Address", "Content Type", "Status Code", "Status", "Indexability"])
        w.writerow(["https://example.com/", "text/html", "200", "OK", "Indexable"])
    res3 = run_audit(input_mode="parse-exports", exports_dir=str(d3), log=lambda m: None)
    assert "CANONICAL_CHAIN" in {s.id for s in res3.skipped}
    assert "CANONICAL_CHAIN" not in {i.check for i in res3.issues}


def test_canonical_to_redirect_fires_and_skips(tmp_path):
    # A's canonical → B, B is a 301 -> fire on A; C's canonical → D (200) -> no fire.
    rows = [
        [
            "https://example.com/a",
            "text/html",
            "200",
            "OK",
            "Indexable",
            TITLE,
            DESC,
            "H",
            "https://example.com/b",
            "",
            "index,follow",
            "",
            "2",
            "Easy",
            "70",
            "12",
            "5",
            "1",
            "500",
        ],
        [
            "https://example.com/b",
            "text/html",
            "301",
            "Redirection (301)",
            "Indexable",
            TITLE,
            DESC,
            "H",
            "",
            "",
            "index,follow",
            "",
            "2",
            "Easy",
            "70",
            "12",
            "5",
            "1",
            "500",
        ],
        [
            "https://example.com/c",
            "text/html",
            "200",
            "OK",
            "Indexable",
            TITLE,
            DESC,
            "H",
            "https://example.com/d",
            "",
            "index,follow",
            "",
            "2",
            "Easy",
            "70",
            "12",
            "5",
            "1",
            "500",
        ],
        [
            "https://example.com/d",
            "text/html",
            "200",
            "OK",
            "Indexable",
            TITLE,
            DESC,
            "H",
            "https://example.com/d",
            "",
            "index,follow",
            "",
            "2",
            "Easy",
            "70",
            "12",
            "5",
            "1",
            "500",
        ],
    ]
    res = _run(tmp_path, rows)
    fired = {}
    for i in res.issues:
        fired.setdefault(i.check, set()).add(i.target_url)
    assert "https://example.com/a" in fired.get("CANONICAL_TO_REDIRECT", set())
    assert "https://example.com/c" not in fired.get("CANONICAL_TO_REDIRECT", set())
    red_issue = next(i for i in res.issues if i.check == "CANONICAL_TO_REDIRECT")
    assert red_issue.details["canonical"] == "https://example.com/b"
    assert red_issue.details["canonical_status_code"] == 301

    # skip case: no canonical data
    d2 = tmp_path / "nocanon2"
    d2.mkdir()
    with open(d2 / "internal_all.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Address", "Content Type", "Status Code", "Status", "Indexability"])
        w.writerow(["https://example.com/", "text/html", "200", "OK", "Indexable"])
    res2 = run_audit(input_mode="parse-exports", exports_dir=str(d2), log=lambda m: None)
    assert "CANONICAL_TO_REDIRECT" in {s.id for s in res2.skipped}


_HREFLANG_INTERNAL_COLS = [
    "Address",
    "Content Type",
    "Status Code",
    "Status",
    "Indexability",
    "Title 1",
    "Meta Description 1",
    "H1-1",
    "Canonical Link Element 1",
    "Meta Robots 1",
]


def test_hreflang_broken_target_fires_and_skips(tmp_path):
    d = tmp_path / "exports"
    d.mkdir()
    with open(d / "internal_all.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(_HREFLANG_INTERNAL_COLS)
        w.writerow(
            [
                "https://example.com/",
                "text/html",
                "200",
                "OK",
                "Indexable",
                TITLE,
                DESC,
                "H",
                "https://example.com/",
                "index,follow",
            ]
        )
        # 404 + 301 hreflang targets (non-indexable, still in the crawl graph)
        w.writerow(
            [
                "https://example.com/en",
                "text/html",
                "404",
                "Not Found",
                "Non-Indexable",
                "",
                "",
                "",
                "",
                "index,follow",
            ]
        )
        w.writerow(
            [
                "https://example.com/ru",
                "text/html",
                "301",
                "Moved",
                "Non-Indexable",
                "",
                "",
                "",
                "",
                "index,follow",
            ]
        )
        # clean 200 target — must NOT be flagged
        w.writerow(
            [
                "https://example.com/de",
                "text/html",
                "200",
                "OK",
                "Indexable",
                TITLE,
                DESC,
                "H",
                "https://example.com/de",
                "index,follow",
            ]
        )
    with open(d / "all_hreflang.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Source", "Destination", "Hreflang"])
        w.writerow(["https://example.com/", "https://example.com/en", "en"])  # 404 -> broken
        w.writerow(["https://example.com/", "https://example.com/ru", "ru"])  # 301 -> broken
        w.writerow(["https://example.com/", "https://example.com/de", "de"])  # 200 -> clean
        w.writerow(
            ["https://example.com/", "https://example.com/external", "fr"]
        )  # not crawled -> skip

    res = run_audit(input_mode="parse-exports", exports_dir=str(d), log=lambda m: None)
    fired = {}
    for i in res.issues:
        fired.setdefault(i.check, set()).add(i.target_url)
    assert fired.get("HREFLANG_BROKEN_TARGET") == {"https://example.com/"}
    issue = next(i for i in res.issues if i.check == "HREFLANG_BROKEN_TARGET")
    targets = {t["target_url"] for t in issue.details["broken_targets"]}
    assert "https://example.com/en" in targets
    assert "https://example.com/ru" in targets
    assert "https://example.com/de" not in targets
    assert issue.occurrences_count == 2

    # skip case: no all_hreflang export -> honest skip, no per-page noise
    d2 = tmp_path / "nohref"
    d2.mkdir()
    with open(d2 / "internal_all.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(_HREFLANG_INTERNAL_COLS)
        w.writerow(
            [
                "https://example.com/",
                "text/html",
                "200",
                "OK",
                "Indexable",
                TITLE,
                DESC,
                "H",
                "https://example.com/",
                "index,follow",
            ]
        )
    res2 = run_audit(input_mode="parse-exports", exports_dir=str(d2), log=lambda m: None)
    assert "HREFLANG_BROKEN_TARGET" in {s.id for s in res2.skipped}
    assert "HREFLANG_BROKEN_TARGET" not in {i.check for i in res2.issues}


def test_hreflang_broken_target_not_masked_by_a_case_only_variant(tmp_path):
    """#202: a live /en must not hide a 404 /EN — norm_url must not fold path case."""
    d = tmp_path / "exports"
    d.mkdir()
    with open(d / "internal_all.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(_HREFLANG_INTERNAL_COLS)
        w.writerow(
            [
                "https://example.test/",
                "text/html",
                "200",
                "OK",
                "Indexable",
                TITLE,
                DESC,
                "H",
                "https://example.test/",
                "index,follow",
            ]
        )
        w.writerow(
            [
                "https://example.test/en",
                "text/html",
                "200",
                "OK",
                "Indexable",
                TITLE,
                DESC,
                "H",
                "https://example.test/en",
                "index,follow",
            ]
        )
        w.writerow(
            [
                "https://example.test/EN",
                "text/html",
                "404",
                "Not Found",
                "Non-Indexable",
                "",
                "",
                "",
                "",
                "",
            ]
        )
    with open(d / "all_hreflang.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Source", "Destination", "Hreflang"])
        w.writerow(["https://example.test/", "https://example.test/EN", "en"])

    res = run_audit(input_mode="parse-exports", exports_dir=str(d), log=lambda m: None)
    fired = {i.check: i.target_url for i in res.issues if i.check == "HREFLANG_BROKEN_TARGET"}
    assert fired.get("HREFLANG_BROKEN_TARGET") == "https://example.test/"


# --- Issue #30: hreflang code/self-reference/x-default/duplicate/canonical quality ---
_HREFLANG_QUALITY_CHECKS = (
    "HREFLANG_INVALID_CODE",
    "HREFLANG_MULTIPLE_ENTRIES",
    "HREFLANG_MISSING_SELF_REFERENCE",
    "HREFLANG_MISSING_XDEFAULT",
    "HREFLANG_NOT_CANONICAL",
)


def _hreflang_quality_internal_row(url, canonical=None):
    return [
        url,
        "text/html",
        "200",
        "OK",
        "Indexable",
        TITLE,
        DESC,
        "H",
        canonical or url,
        "index,follow",
    ]


def test_hreflang_quality_checks_fire(tmp_path):
    d = tmp_path / "exports"
    d.mkdir()
    with open(d / "internal_all.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(_HREFLANG_INTERNAL_COLS)
        # "hub" declares a whole alternates set but never references itself,
        # never declares x-default, duplicates "es", and uses an invalid code.
        w.writerow(_hreflang_quality_internal_row("https://example.com/hub"))
        w.writerow(_hreflang_quality_internal_row("https://example.com/en"))
        w.writerow(_hreflang_quality_internal_row("https://example.com/es-a"))
        w.writerow(_hreflang_quality_internal_row("https://example.com/es-b"))
        # the hub's "de" alternate is a duplicate that itself canonicalizes
        # elsewhere -> HREFLANG_NOT_CANONICAL.
        w.writerow(
            _hreflang_quality_internal_row(
                "https://example.com/de-dup", canonical="https://example.com/de-canonical"
            )
        )
        w.writerow(_hreflang_quality_internal_row("https://example.com/de-canonical"))
        # a clean, well-formed two-page cluster: self-reference + x-default
        # both present, no duplicates, no invalid codes -> nothing fires.
        w.writerow(_hreflang_quality_internal_row("https://example.com/clean-en"))
        w.writerow(_hreflang_quality_internal_row("https://example.com/clean-fr"))

    with open(d / "all_hreflang.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Source", "Destination", "Hreflang"])
        hub = "https://example.com/hub"
        w.writerow([hub, "https://example.com/en", "en"])
        w.writerow([hub, "https://example.com/es-a", "es"])
        w.writerow([hub, "https://example.com/es-b", "es"])  # duplicate "es"
        w.writerow([hub, "https://example.com/de-dup", "de"])  # not canonical
        w.writerow([hub, "https://example.com/fr-x", "fr-XX"])  # invalid region

        clean_en, clean_fr = "https://example.com/clean-en", "https://example.com/clean-fr"
        for src in (clean_en, clean_fr):
            w.writerow([src, clean_en, "en"])
            w.writerow([src, clean_fr, "fr"])
            w.writerow([src, clean_en, "x-default"])

    res = run_audit(input_mode="parse-exports", exports_dir=str(d), log=lambda m: None)
    fired: dict[str, set[str]] = {}
    for i in res.issues:
        fired.setdefault(i.check, set()).add(i.target_url)

    assert fired.get("HREFLANG_INVALID_CODE") == {"https://example.com/hub"}
    invalid = next(i for i in res.issues if i.check == "HREFLANG_INVALID_CODE")
    assert invalid.details["invalid"][0]["hreflang"] == "fr-XX"

    assert fired.get("HREFLANG_MULTIPLE_ENTRIES") == {"https://example.com/hub"}
    dup = next(i for i in res.issues if i.check == "HREFLANG_MULTIPLE_ENTRIES")
    assert dup.details["duplicate_values"] == ["es"]

    assert fired.get("HREFLANG_MISSING_SELF_REFERENCE") == {"https://example.com/hub"}
    assert fired.get("HREFLANG_MISSING_XDEFAULT") == {"https://example.com/hub"}

    assert fired.get("HREFLANG_NOT_CANONICAL") == {"https://example.com/hub"}
    non_canon = next(i for i in res.issues if i.check == "HREFLANG_NOT_CANONICAL")
    offender = non_canon.details["non_canonical_targets"][0]
    assert offender["destination"] == "https://example.com/de-dup"
    assert offender["canonical"] == "https://example.com/de-canonical"

    # the clean cluster trips none of the five checks
    for check_id in _HREFLANG_QUALITY_CHECKS:
        assert "https://example.com/clean-en" not in fired.get(check_id, set())
        assert "https://example.com/clean-fr" not in fired.get(check_id, set())


def test_hreflang_quality_checks_skip_without_export(tmp_path):
    d = tmp_path / "exports"
    d.mkdir()
    with open(d / "internal_all.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(_HREFLANG_INTERNAL_COLS)
        w.writerow(_hreflang_quality_internal_row("https://example.com/"))
    res = run_audit(input_mode="parse-exports", exports_dir=str(d), log=lambda m: None)
    skipped_ids = {s.id for s in res.skipped}
    fired_ids = {i.check for i in res.issues}
    for check_id in _HREFLANG_QUALITY_CHECKS:
        assert check_id in skipped_ids
        assert check_id not in fired_ids
