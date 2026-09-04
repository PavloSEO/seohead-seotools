"""Properties that only exist *between* stages of a chain.

1695 tests, and every defect found on a live site survived all of them. That is not bad luck:
each test takes one module, hands it a fixture, and checks its output, while every one of those
defects lived in a handoff.

| # | Both sides correct alone | What broke between them |
|---|---|---|
| #99 | `response.text` decodes correctly; `len()` measures correctly | the size was taken after the decode |
| #94 | the link graph is right; `reconcile_sitemap` is right | the graph was the wrong population to hand it |
| #95 | `norm_url` is correctly tolerant; a dict is a correct index | a many-to-one key used one-to-one |
| #96 | `resolve_content_area` returns what it was asked for | nobody asked it for the right region |

So these tests crawl a whole fixture site over loopback and assert four properties of the run
as a whole: conservation, population, determinism and representation. The rules are the same
ones `seohead.tools.logscan` applies to a real run after the fact — written once, used from
both ends.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from seohead.servers import handlers
from seohead.tools import logscan
from tests.chains.chain_site import PHOTO_BYTES, run_chain_site


@pytest.fixture(scope="module")
def site(monkeypatch_module):
    # The crawler refuses private-network targets unless explicitly authorized; a loopback
    # fixture is exactly the case that authorization exists for.
    monkeypatch_module.setenv("SEOHEAD_ALLOW_PRIVATE_NETWORKS", "1")
    with run_chain_site() as base_url:
        yield base_url


@pytest.fixture(scope="module")
def monkeypatch_module():
    from _pytest.monkeypatch import MonkeyPatch

    patch = MonkeyPatch()
    yield patch
    patch.undo()


def _crawl(base_url: str, out_dir: Path, **kwargs):
    return handlers.crawl_site(
        url=f"{base_url}/", out_dir=str(out_dir), max_urls=30, config=None, **kwargs
    )


def _pages(out_dir: Path) -> list[dict]:
    lines = (out_dir / "pages.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _by_url(pages: list[dict]) -> dict[str, dict]:
    return {p["url"]: p for p in pages}


@pytest.fixture(scope="module")
def crawled(site, tmp_path_factory):
    """One crawl, reused by every property below — the same discipline the scenarios ask of a
    user: crawl once, answer many questions from what it collected."""
    out = tmp_path_factory.mktemp("chain-run")
    result = _crawl(site, out)
    return result, out, _pages(out)


# ── 1. Conservation: a number must not change meaning as it travels ──────────


def test_the_bytes_on_the_wire_are_the_bytes_in_the_record(site, crawled):
    """The binary asset is the case that broke: its decoded length is far larger than its
    body, and for a long time the larger number is what the record carried (#99)."""
    _result, _out, pages = crawled
    photo = _by_url(pages).get(f"{site}/photo.webp")
    assert photo is not None, "the crawl must reach the linked image"
    assert photo["size_bytes"] == len(PHOTO_BYTES)
    # And the inflation is real on this fixture, so the assertion above is not vacuous.
    inflated = len(PHOTO_BYTES.decode("utf-8", "replace").encode("utf-8"))
    assert inflated > len(PHOTO_BYTES) * 1.5


def test_a_legacy_charset_page_is_measured_by_its_bytes(site, crawled):
    _result, _out, pages = crawled
    legacy = _by_url(pages).get(f"{site}/legacy")
    assert legacy is not None
    # windows-1251 stores one byte per Cyrillic character; UTF-8 stores two. If the record
    # carried the decoded length it would be visibly larger than the response body.
    assert legacy["size_bytes"] > 0
    text_len = len((legacy.get("title") or "").encode("utf-8"))
    assert text_len < legacy["size_bytes"]


def test_the_text_ratio_is_a_percentage_of_the_same_bytes(crawled):
    _result, _out, pages = crawled
    for page in pages:
        ratio = page.get("text_ratio")
        if ratio is None:
            continue
        assert 0 <= ratio <= 100, (page["url"], ratio)


def test_the_size_survives_the_projection_into_the_audit(crawled):
    """pages.jsonl and the audit's own page table are two views of one measurement."""
    result, _out, pages = crawled
    recorded = {p["url"]: p["size_bytes"] for p in pages}
    for page in result.get("pages") or []:
        size = (page.get("metrics") or {}).get("size_bytes")
        if size is None or page["url"] not in recorded:
            continue
        assert size == recorded[page["url"]], page["url"]


# ── 2. Population: a finding is about a member of the set it describes ───────


def test_every_finding_targets_a_url_this_run_actually_fetched(crawled):
    _result, out, _pages = crawled
    report = logscan.scan(logscan.load_run(str(out)))
    offenders = [a for a in report["anomalies"] if a["rule"] == "findings_are_about_crawled_urls"]
    assert offenders == [], offenders


def test_no_check_fires_more_often_than_its_own_population(crawled):
    _result, out, _pages = crawled
    report = logscan.scan(logscan.load_run(str(out)))
    offenders = [a for a in report["anomalies"] if a["rule"] == "check_within_its_population"]
    assert offenders == [], offenders


def test_the_whole_run_contradicts_itself_nowhere(crawled):
    """The scanner's rules, applied to a run this suite produced. A chain test that passes
    while log-scan reports a contradiction would mean the two disagree about what is true."""
    _result, out, _pages = crawled
    report = logscan.scan(logscan.load_run(str(out)))
    assert report["anomaly_count"] == 0, report["anomalies"]


def test_an_off_host_link_is_recorded_and_never_fetched(site, crawled):
    result, _out, pages = crawled
    fetched_hosts = {urlsplit(p["url"]).hostname for p in pages}
    assert "other.example" not in fetched_hosts
    assert result["discovery"]["excluded"].get("outside_host", 0) >= 1


def test_a_robots_disallowed_path_is_excluded_and_counted(site, crawled):
    result, _out, pages = crawled
    assert f"{site}/private/" not in _by_url(pages)
    assert result["discovery"]["robots_blocked"] >= 1


# ── 3. Determinism: the same site, twice, is the same answer ─────────────────


def _comparable(pages: list[dict]) -> list[tuple]:
    return sorted(
        (p["url"], p.get("status_code"), p.get("size_bytes"), p.get("word_count")) for p in pages
    )


def test_two_crawls_of_one_site_produce_identical_records(site, tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    _crawl(site, first)
    _crawl(site, second)
    assert _comparable(_pages(first)) == _comparable(_pages(second))


def test_concurrency_changes_the_pace_not_the_answer(site, tmp_path):
    sequential = tmp_path / "sequential"
    parallel = tmp_path / "parallel"
    _crawl(site, sequential, concurrency=1)
    _crawl(site, parallel, concurrency=4)
    assert _comparable(_pages(sequential)) == _comparable(_pages(parallel))


# ── 4. Representation: numbers say how they were measured ────────────────────


def test_every_page_records_how_it_was_measured(crawled):
    _result, _out, pages = crawled
    unlabelled = [p["url"] for p in pages if not p.get("representation")]
    assert unlabelled == []


def test_the_content_region_is_named_per_page_not_assumed(site):
    """The home page carries a masthead and a skip link outside <main>. Which region was used
    is a per-page fact, and it must be reported rather than inferred by the reader (#96)."""
    page = handlers.parse(url=f"{site}/")["results"][0]
    assert page["content_area_strategy"] == "auto_main"
    # ``text`` is the whole document; ``content_text`` is the region the strategy chose. The
    # two must differ on this page, or the strategy would be a label with no consequence.
    content = page.get("content_text") or ""
    assert "Skip to content" not in content
    assert "555 0100" not in content
    assert "body of the home page" in content
    assert "Skip to content" in (page.get("text") or "")
    assert page["word_count"] == len(content.split())


# ── the sitemap-seeded chain: a second population enters the run ─────────────


@pytest.fixture(scope="module")
def crawled_with_sitemap(site, tmp_path_factory):
    out = tmp_path_factory.mktemp("chain-sitemap-run")
    result = handlers.crawl_site(
        url=f"{site}/", sitemap=f"{site}/sitemap.xml", out_dir=str(out), max_urls=30
    )
    return result, out, _pages(out)


def test_the_sitemap_comparison_stays_inside_the_pages_it_describes(crawled_with_sitemap):
    """The fixture links to an image file, an off-host URL and a robots-disallowed path.
    None of the three is a page a sitemap of pages should declare, and reporting them was 74%
    of one live report (#94)."""
    _result, _out, _ = crawled_with_sitemap
    summary = _result["summary"]["sitemap"]
    for reported in summary["linked_not_in_sitemap"]:
        assert not reported.endswith(".webp"), reported
        assert urlsplit(reported).hostname != "other.example", reported
        assert "/private/" not in reported, reported


@pytest.mark.xfail(
    strict=True,
    reason="#115: the sitemap seeder normalises the trailing slash away, so the crawl "
    "fetches /orphan instead of the declared /orphan/ and the orphan is named in a form "
    "the site never published. Remove this marker when #115 lands.",
)
def test_a_declared_url_nothing_links_to_is_still_reported_as_an_orphan(site, crawled_with_sitemap):
    """Narrowing the comparable side must not cost the mirror-image finding."""
    _result, _out, _ = crawled_with_sitemap
    assert f"{site}/orphan/" in _result["summary"]["sitemap"]["in_sitemap_not_linked"]


def test_the_sitemap_run_contradicts_itself_nowhere(crawled_with_sitemap):
    _result, out, _ = crawled_with_sitemap
    report = logscan.scan(logscan.load_run(str(out)))
    assert report["anomaly_count"] == 0, report["anomalies"]


def test_a_canonical_pointing_at_the_slashless_twin_is_not_called_a_redirect(
    site, crawled_with_sitemap
):
    """Both /a and /a/ are in this crawl, and /b/ canonicalises to the one that 301s. The
    normalised index holds both, so the claim 'this canonical is a redirect' is false (#95)."""
    result, _out, pages = crawled_with_sitemap
    urls = _by_url(pages)
    assert urls[f"{site}/a"]["status_code"] == 301, "the fixture must serve both slash forms"
    assert urls[f"{site}/a/"]["status_code"] == 200
    offenders = [
        issue
        for issue in (result.get("issues") or [])
        if issue.get("check") == "CANONICAL_TO_REDIRECT"
    ]
    assert offenders == [], offenders
