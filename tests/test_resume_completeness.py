"""Every accumulator a crawl builds up must survive its own checkpoint.

Three separate defects in this repository were the same omission: a field was
added to ``SpiderResult``, the checkpoint was not extended to carry it, and a
resumed crawl silently reported less than an uninterrupted one. #141 lost the
link graph, the exclusion tally and the query-variant budget; #188 lost form
findings and the start page's rendering evidence. Each was found on a live run,
long after the field was added.

The list below is the fix for the pattern rather than for the two fields: every
field on ``SpiderResult`` must be classified here, so adding a new one to the
dataclass without deciding how it survives a resume fails immediately, by name.
"""

from __future__ import annotations

import dataclasses

from seohead.crawl.spider import SpiderResult

# Carried inside crawl_state.json.
CHECKPOINTED = {"excluded", "max_depth_reached", "forms", "start_page_evidence"}

# Written to their own sidecar file as they are produced and read back on
# resume, because they are the two structures large enough that reserialising
# them on every checkpoint would dominate the cost of taking one.
SIDECAR = {"pages", "links"}

# Recomputed from scratch on every invocation, so carrying them would be wrong,
# not merely unnecessary: each describes this call, not the crawl as a whole.
PER_INVOCATION = {
    # A constant describing the output format, not crawl state.
    "schema_version",
    "resume_note",
    "resumed",
    "partial",
    "stopped_reason",
    "finish_reason",
    "effective_delay",
    "effective_concurrency",
    "crawl_delay_applied",
    "robots_note",
    "robots_blocked",
    "seed_urls",
    "limitations",
    "cache_stats",
    "cache_replay",
}


def test_every_spider_result_field_is_classified_for_resume():
    """A new field on SpiderResult must be placed in one of the three groups above.

    Failing here is the point: the alternative is discovering months later, on a
    real crawl, that a resumed run quietly reports less than an uninterrupted one.
    """
    known = CHECKPOINTED | SIDECAR | PER_INVOCATION
    actual = {f.name for f in dataclasses.fields(SpiderResult)}
    unclassified = actual - known
    assert not unclassified, (
        f"new SpiderResult field(s) {sorted(unclassified)}: decide whether each survives a "
        "resume (add to CHECKPOINTED and to crawl_state.CrawlState), lives in a sidecar, or "
        "is genuinely per-invocation — see issue #188"
    )
    stale = known - actual
    assert not stale, f"classified field(s) no longer on SpiderResult: {sorted(stale)}"


def test_the_checkpoint_carries_every_field_it_claims_to():
    """CHECKPOINTED above and CrawlState must not drift apart: a field listed here but
    absent from the state dataclass would read as handled while being dropped."""
    from seohead.crawl.state import CrawlState

    state_fields = {f.name for f in dataclasses.fields(CrawlState)}
    missing = CHECKPOINTED - state_fields
    assert not missing, f"claimed checkpointed but absent from CrawlState: {sorted(missing)}"
