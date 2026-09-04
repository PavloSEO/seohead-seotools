"""The anomaly scanner: contradictions inside one run's own artifacts.

Each rule here exists because a defect shipped past 1600 tests and was caught by a person
reading a number that could not be true. The fixture below carries one instance of each, so a
regression in a rule is a failing test rather than another afternoon of reading reports.
"""

from __future__ import annotations

import json

from seohead.servers import handlers
from seohead.tools import logscan


def _write_run(tmp_path, pages, audit):
    (tmp_path / "pages.jsonl").write_text(
        "\n".join(json.dumps(p) for p in pages) + "\n", encoding="utf-8"
    )
    (tmp_path / "audit.json").write_text(json.dumps(audit), encoding="utf-8")
    return str(tmp_path)


def _page(url, **kw):
    base = {
        "url": url,
        "status_code": 200,
        "content_type": "text/html; charset=utf-8",
        "size_bytes": 1000,
        "word_count": 100,
        "text_ratio": 40.0,
        "representation": "static",
    }
    base.update(kw)
    return base


def _clean_run(tmp_path):
    pages = [_page(f"https://example.com/p{i}") for i in range(4)]
    audit = {
        "summary": {"by_check": {"THIN_CONTENT": 1}},
        "issues": [{"check": "THIN_CONTENT", "target_url": "https://example.com/p0"}],
    }
    return _write_run(tmp_path, pages, audit)


def test_a_clean_run_reports_nothing(tmp_path):
    result = logscan.scan(logscan.load_run(_clean_run(tmp_path)))
    assert result["anomaly_count"] == 0
    assert result["anomalies"] == []
    # A clean result must not be mistakable for an unchecked one.
    assert len(result["rules_run"]) == len(logscan.RULES)
    assert result["read"]["pages"] == 4


# ── #99: a size that disagrees with the bytes ────────────────────────────────


def test_a_recorded_size_that_disagrees_with_the_downloaded_file(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    images = tmp_path / "images"
    images.mkdir()
    (images / "photo.webp").write_bytes(b"x" * 738968)
    (images / "manifest.json").write_text(
        json.dumps({"images": [{"url": "https://example.com/photo.webp", "path": "photo.webp"}]}),
        encoding="utf-8",
    )
    pages = [
        _page(
            "https://example.com/photo.webp",
            content_type="image/webp",
            size_bytes=1270855,  # the inflated figure the decoded-text measurement produced
            word_count=0,
            text_ratio=None,
        )
    ]
    _write_run(run_dir, pages, {"summary": {"by_check": {}}, "issues": []})

    result = logscan.scan(logscan.load_run(str(run_dir), str(images)))

    found = [a for a in result["anomalies"] if a["rule"] == "size_matches_file"]
    assert len(found) == 1
    assert found[0]["observed"] == 1270855
    assert found[0]["expected"] == 738968


def test_a_text_ratio_over_one_hundred_percent(tmp_path):
    pages = [_page("https://example.com/", text_ratio=173.0)]
    run = _write_run(tmp_path, pages, {"summary": {"by_check": {}}, "issues": []})
    result = logscan.scan(logscan.load_run(run))
    assert [a["rule"] for a in result["anomalies"]] == ["text_ratio_is_a_percentage"]


def test_words_counted_on_a_page_with_no_bytes(tmp_path):
    pages = [_page("https://example.com/", size_bytes=0, word_count=250, text_ratio=None)]
    run = _write_run(tmp_path, pages, {"summary": {"by_check": {}}, "issues": []})
    result = logscan.scan(logscan.load_run(run))
    assert [a["rule"] for a in result["anomalies"]] == ["words_without_bytes"]


# ── #94: a check compared against the wrong population ───────────────────────


def test_a_finding_about_a_url_the_run_never_fetched(tmp_path):
    pages = [_page("https://example.com/")]
    audit = {
        "summary": {"by_check": {"URL_NOT_IN_SITEMAP": 1}},
        "issues": [{"check": "URL_NOT_IN_SITEMAP", "target_url": "https://wa.me/123"}],
    }
    run = _write_run(tmp_path, pages, audit)
    result = logscan.scan(logscan.load_run(run))
    found = [a for a in result["anomalies"] if a["rule"] == "findings_are_about_crawled_urls"]
    assert len(found) == 1
    assert found[0]["target"] == "https://wa.me/123"


def test_a_check_that_fires_more_often_than_there_are_pages(tmp_path):
    pages = [_page(f"https://example.com/p{i}") for i in range(3)]
    audit = {
        "summary": {"by_check": {"URL_NOT_IN_SITEMAP": 9}},
        "issues": [
            {"check": "URL_NOT_IN_SITEMAP", "target_url": f"https://example.com/p{i % 3}"}
            for i in range(9)
        ],
    }
    run = _write_run(tmp_path, pages, audit)
    result = logscan.scan(logscan.load_run(run))
    found = [a for a in result["anomalies"] if a["rule"] == "check_within_its_population"]
    assert len(found) == 1
    assert found[0]["observed"] == 9
    assert found[0]["expected"] == 3


def test_a_check_that_deliberately_names_uncrawled_urls_is_not_flagged(tmp_path):
    """SITEMAP_ORPHAN is *about* a URL nothing linked to; that is not a contradiction."""
    pages = [_page("https://example.com/")]
    audit = {
        "summary": {"by_check": {"SITEMAP_ORPHAN": 1}},
        "issues": [{"check": "SITEMAP_ORPHAN", "target_url": "https://example.com/declared"}],
    }
    run = _write_run(tmp_path, pages, audit)
    assert logscan.scan(logscan.load_run(run))["anomaly_count"] == 0


# ── #95: a canonical whose twin answered ─────────────────────────────────────


def test_canonical_reported_as_a_redirect_while_that_url_answered_200(tmp_path):
    pages = [
        _page("https://example.com/post"),
        _page("https://example.com/author/name/"),
        _page(
            "https://example.com/author/name",
            status_code=301,
            word_count=0,
            text_ratio=None,
            size_bytes=0,
        ),
    ]
    audit = {
        "summary": {"by_check": {"CANONICAL_TO_REDIRECT": 1}},
        "issues": [
            {
                "check": "CANONICAL_TO_REDIRECT",
                "target_url": "https://example.com/post",
                "details": {"canonical": "https://example.com/author/name/"},
            }
        ],
    }
    run = _write_run(tmp_path, pages, audit)
    result = logscan.scan(logscan.load_run(run))
    rules = {a["rule"] for a in result["anomalies"]}
    assert "canonical_to_redirect_has_no_answering_twin" in rules


# ── bookkeeping contradictions ───────────────────────────────────────────────


def test_a_summary_that_disagrees_with_its_own_rows(tmp_path):
    pages = [_page(f"https://example.com/p{i}") for i in range(5)]
    audit = {
        "summary": {"by_check": {"THIN_CONTENT": 4}},
        "issues": [{"check": "THIN_CONTENT", "target_url": "https://example.com/p0"}],
    }
    run = _write_run(tmp_path, pages, audit)
    result = logscan.scan(logscan.load_run(run))
    found = [a for a in result["anomalies"] if a["rule"] == "summary_matches_detail"]
    assert len(found) == 1
    assert found[0]["observed"] == 4
    assert found[0]["expected"] == 1


def test_pages_measured_two_ways_where_only_some_say_which(tmp_path):
    pages = [_page("https://example.com/a"), _page("https://example.com/b", representation="")]
    run = _write_run(tmp_path, pages, {"summary": {"by_check": {}}, "issues": []})
    result = logscan.scan(logscan.load_run(run))
    assert [a["rule"] for a in result["anomalies"]] == ["representation_is_recorded"]


# ── the handler ──────────────────────────────────────────────────────────────


def test_the_handler_refuses_a_directory_with_no_artifacts(tmp_path):
    out = handlers.log_scan(run=str(tmp_path))
    assert out["ok"] is False
    assert "no audit.json or pages.jsonl" in out["error"]


def test_the_handler_reads_a_run_directory(tmp_path):
    out = handlers.log_scan(run=_clean_run(tmp_path))
    assert out["ok"] is True
    assert out["anomaly_count"] == 0


def test_repeated_copies_of_one_contradiction_are_capped_but_counted(tmp_path):
    pages = [_page(f"https://example.com/p{i}", text_ratio=150.0) for i in range(30)]
    run = _write_run(tmp_path, pages, {"summary": {"by_check": {}}, "issues": []})
    result = logscan.scan(logscan.load_run(run), max_per_rule=5)
    assert len(result["anomalies"]) == 5
    assert result["by_rule"]["text_ratio_is_a_percentage"] == 30


# ── the CLI gate ─────────────────────────────────────────────────────────────


def test_the_cli_exits_two_when_a_run_contradicts_itself(tmp_path, capsys):
    from seohead.cli import main

    pages = [_page("https://example.com/", text_ratio=150.0)]
    run = _write_run(tmp_path, pages, {"summary": {"by_check": {}}, "issues": []})
    assert main(["log-scan", "--run", run]) == 2
    assert "text_ratio_is_a_percentage" in capsys.readouterr().out


def test_the_cli_exits_zero_on_a_clean_run(tmp_path):
    from seohead.cli import main

    assert main(["log-scan", "--run", _clean_run(tmp_path)]) == 0
