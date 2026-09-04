"""Internal link score over a completed internal follow-link graph.

One new edge changes every page's score, so this is inherently a whole-graph
computation: it cannot be kept current while a crawl is still discovering
pages, and can only run as a second pass once the crawl (and therefore the
edge list) is finished (issue #15, item 1). Re-running after the crawl is
free, since the graph is already stored.

The algorithm is the standard PageRank power-iteration: each URL starts with
an equal share of the total score, and on every round redistributes it evenly
across its own internal follow outlinks. A page with no internal follow
outlink (a "dangling" node) would otherwise leak its score out of the system
each round, so its share is instead redistributed evenly across every page —
the conventional dangling-node fix, and the reason the total score is exactly
conserved every round.
"""

from __future__ import annotations

# The classic PageRank damping factor: the probability a random "surfer"
# keeps following links rather than jumping to an arbitrary page.
DEFAULT_DAMPING = 0.85
DEFAULT_MAX_ITERATIONS = 200
# Converged once no node's score moves more than this between rounds; a
# contraction mapping with damping < 1 always reaches this, so a fixed
# tolerance (rather than a fixed iteration count) is what makes the result a
# genuine fixed point instead of an arbitrary partial computation.
DEFAULT_TOLERANCE = 1e-10


def compute_link_scores(
    edges: list[tuple[str, str]],
    urls: set[str] | None = None,
    damping: float = DEFAULT_DAMPING,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    tolerance: float = DEFAULT_TOLERANCE,
) -> dict[str, float]:
    """Return each node's internal link score; scores over all nodes sum to 1.

    ``edges`` is the internal, followed edge list only — filtering out
    external destinations and nofollow links is the caller's job, since only
    it knows the export's own Type/Follow columns. ``urls`` adds nodes with no
    edges at all (an internal page with zero measured in- or out-links still
    holds a share of the total score); it defaults to the nodes ``edges``
    itself mentions.
    """
    nodes = set(urls) if urls is not None else set()
    for a, b in edges:
        nodes.add(a)
        nodes.add(b)
    if not nodes:
        return {}
    n = len(nodes)

    outdegree: dict[str, int] = dict.fromkeys(nodes, 0)
    adjacency: dict[str, list[str]] = {u: [] for u in nodes}
    for a, b in edges:
        if a == b:
            continue  # a link to oneself carries no distinct evidence
        adjacency[a].append(b)
        outdegree[a] += 1

    score = dict.fromkeys(nodes, 1.0 / n)
    base = (1.0 - damping) / n
    dangling = [u for u in nodes if outdegree[u] == 0]

    for _ in range(max_iterations):
        dangling_mass = sum(score[u] for u in dangling)
        next_score = dict.fromkeys(nodes, base + damping * dangling_mass / n)
        for u in nodes:
            if outdegree[u] == 0:
                continue
            share = damping * score[u] / outdegree[u]
            for v in adjacency[u]:
                next_score[v] += share
        delta = max(abs(next_score[u] - score[u]) for u in nodes)
        score = next_score
        if delta < tolerance:
            break
    return score
