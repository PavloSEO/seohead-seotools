"""Issue #141, end to end on the real chain fixture: a crawl interrupted and resumed must
report the same link graph and exclusion tally as one that ran straight through, and the
query-variant budget must hold across the checkpoint rather than reopening on every call.

Driven through ``seohead.crawl.spider.crawl_site`` directly rather than
``handlers.crawl_site``, so ``config_fingerprint`` is the fixed string this test controls —
the same identity across both calls, the way a real resumable-crawl driver keeps a checkpoint
valid across two invocations of the same logical crawl regardless of how big a slice
(``max_urls``) any one process gets through.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from seohead.crawl.spider import crawl_site
from tests.chains.chain_site import run_chain_site


@pytest.fixture
def site(monkeypatch):
    # The crawler refuses private-network targets unless explicitly authorized; a loopback
    # fixture is exactly the case that authorization exists for.
    monkeypatch.setenv("SEOHEAD_ALLOW_PRIVATE_NETWORKS", "1")
    with run_chain_site() as base_url:
        yield base_url


def _crawl(base_url: str, max_urls: int, out_dir: Path | None = None):
    kwargs = {}
    if out_dir is not None:
        kwargs["state_path"] = str(out_dir / "state.json")
        kwargs["links_path"] = str(out_dir / "links.jsonl")
        kwargs["out_path"] = str(out_dir / "pages.jsonl")
    return crawl_site(
        f"{base_url}/",
        max_urls=max_urls,
        min_delay=0,
        sleeper=lambda _s: None,
        config_fingerprint="chain-fixture",
        **kwargs,
    )


def test_a_crawl_interrupted_at_two_pages_and_resumed_matches_an_uninterrupted_crawl(
    site, tmp_path
):
    full = _crawl(site, max_urls=30)
    assert full.partial is False
    assert len(full.pages) == 7
    assert len(full.links) == 11
    assert full.excluded == {"outside_host": 1, "blocked_by_robots": 1}

    out_dir = tmp_path / "run"
    out_dir.mkdir()
    part = _crawl(site, max_urls=2, out_dir=out_dir)
    assert part.partial is True
    assert len(part.pages) == 2

    resumed = _crawl(site, max_urls=30, out_dir=out_dir)
    assert resumed.resumed is True
    assert resumed.partial is False
    assert len(resumed.pages) == 7
    assert len(resumed.links) == 11
    assert resumed.excluded == {"outside_host": 1, "blocked_by_robots": 1}

    def edges(result):
        return sorted((edge.source, edge.destination) for edge in result.links)

    assert edges(resumed) == edges(full)
