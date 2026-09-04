"""Internal link score: the iterative whole-graph computation from issue #15
item 1. ``compute_link_scores`` is pure and network-free, so a fixture graph
with a known analytical answer can assert exact values; ``check_link_score``
wires it to the ``all_inlinks`` export it needs and honestly skips without it.
"""

from __future__ import annotations

import csv

import pytest

from seohead.sf.core.audit import run_audit
from seohead.sf.core.link_score import compute_link_scores

# -- pure algorithm ---------------------------------------------------------


def test_a_mutual_pair_splits_the_score_evenly():
    # A symmetric two-node graph has an exact known fixed point regardless of
    # damping: by symmetry each node holds exactly half the total score.
    scores = compute_link_scores([("a", "b"), ("b", "a")])
    assert scores["a"] == pytest.approx(0.5, abs=1e-9)
    assert scores["b"] == pytest.approx(0.5, abs=1e-9)


def test_total_score_is_conserved_across_a_dangling_node():
    # c has no outlink at all; without the dangling-node fix its score would
    # leak out of the system each round instead of being redistributed.
    scores = compute_link_scores([("a", "b"), ("b", "c")])
    assert sum(scores.values()) == pytest.approx(1.0, abs=1e-9)


def test_a_hub_scores_higher_than_an_unlinked_page():
    edges = [("a", "hub"), ("b", "hub"), ("c", "hub"), ("hub", "a")]
    scores = compute_link_scores(edges, urls={"a", "b", "c", "hub", "isolated"})
    assert scores["hub"] > scores["a"]
    assert scores["a"] > scores["isolated"]


def test_urls_with_no_edges_still_receive_a_share():
    # An internal page with zero measured in- or out-links must still exist
    # in the distribution — it is a real node, not an absence.
    scores = compute_link_scores([("a", "b")], urls={"a", "b", "lonely"})
    assert "lonely" in scores
    assert scores["lonely"] > 0


def test_self_links_are_ignored():
    with_self_link = compute_link_scores([("a", "b"), ("b", "b")])
    without_self_link = compute_link_scores([("a", "b")])
    assert with_self_link == pytest.approx(without_self_link, abs=1e-9)


def test_empty_graph_returns_no_scores():
    assert compute_link_scores([]) == {}


# -- wired into the audit ---------------------------------------------------

INTERNAL_COLS = ["Address", "Content Type", "Status Code", "Status", "Indexability", "Crawl Depth"]
INLINK_COLS = ["Source", "Destination", "Type", "Follow"]


def _write(tmp_path, internal_rows, inlink_rows):
    d = tmp_path / "exports"
    d.mkdir()
    with open(d / "internal_all.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(INTERNAL_COLS)
        w.writerows(internal_rows)
    with open(d / "all_inlinks.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(INLINK_COLS)
        w.writerows(inlink_rows)
    return str(d)


def test_link_score_skips_without_the_all_inlinks_export(tmp_path):
    d = tmp_path / "exports"
    d.mkdir()
    with open(d / "internal_all.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(INTERNAL_COLS)
        w.writerow(["https://example.com/", "text/html", "200", "OK", "Indexable", "0"])
    res = run_audit(input_mode="parse-exports", exports_dir=str(d), log=lambda m: None)
    reasons = {s.id: s.reason for s in res.skipped}
    assert "all_inlinks" in reasons["LOW_LINK_SCORE"]


def test_a_page_reached_only_by_nofollow_links_scores_low(tmp_path):
    # Six "core" pages fully interlink with ordinary follow links, so real
    # link equity concentrates among them; "nofollowed" is linked from every
    # one of them, but every one of those links is nofollow, so none of that
    # equity ever reaches it. A raw inlink count would call it exactly as
    # linked as any core page (six inlinks each); only the graph computation
    # tells them apart, scoring "nofollowed" at the site's own unlinked-page
    # floor, far below the interlinked core's median.
    internal_rows = [["https://example.com/", "text/html", "200", "OK", "Indexable", "0"]]
    inlink_rows = []
    cores = [f"https://example.com/core{i}" for i in range(6)]
    for url in cores:
        internal_rows.append([url, "text/html", "200", "OK", "Indexable", "1"])
        inlink_rows.append(["https://example.com/", url, "Hyperlink", "true"])
    for source in cores:
        for dest in cores:
            if source != dest:
                inlink_rows.append([source, dest, "Hyperlink", "true"])
        inlink_rows.append([source, "https://example.com/nofollowed", "Hyperlink", "false"])
    internal_rows.append(
        ["https://example.com/nofollowed", "text/html", "200", "OK", "Indexable", "2"]
    )
    exports_dir = _write(tmp_path, internal_rows, inlink_rows)
    res = run_audit(input_mode="parse-exports", exports_dir=exports_dir, log=lambda m: None)
    low = {i.target_url for i in res.issues if i.check == "LOW_LINK_SCORE"}
    assert "https://example.com/nofollowed" in low
    assert "https://example.com/core0" not in low
