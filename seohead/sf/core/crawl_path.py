"""Shortest discovery route from a seed, over a completed internal link graph.

Screaming Frog's own Crawl Depth column already reports each page's distance
from the start URL, but not the actual route — and the route can only be
reconstructed once the whole graph is on hand, since any edge on the path may
not have been fetched yet mid-crawl (issue #15, item 10). A breadth-first walk
from the seed is the standard way to recover a shortest path once the graph is
static, and it costs no requests to re-run against a stored graph.
"""

from __future__ import annotations

from collections import deque


def shortest_paths_from_seed(edges: list[tuple[str, str]], seed: str) -> dict[str, list[str]]:
    """Return ``{url: [seed, ..., url]}`` for every node reachable from ``seed``.

    Breadth-first, so each path is a shortest path by hop count. A node
    ``edges`` never reaches from ``seed`` has no entry — it cannot be handed a
    discovery route from a graph that does not connect it. The seed itself
    maps to ``[seed]``, a path of zero hops.
    """
    adjacency: dict[str, list[str]] = {}
    for a, b in edges:
        adjacency.setdefault(a, []).append(b)

    paths: dict[str, list[str]] = {seed: [seed]}
    queue: deque[str] = deque([seed])
    while queue:
        current = queue.popleft()
        for neighbor in adjacency.get(current, ()):
            if neighbor in paths:
                continue  # already reached by an earlier, equal-or-shorter path
            paths[neighbor] = [*paths[current], neighbor]
            queue.append(neighbor)
    return paths
