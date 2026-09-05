"""K-Means must produce the number of clusters that was asked for.

Issue #234: the cap was ``min(n_clusters, n_keywords - 1)``, one below what the
corpus can actually support, so a caller asking for two clusters of two keywords
got one and was told nothing. The off-by-one only shows at the boundary, which
is exactly where a small keyword set lives.
"""

from __future__ import annotations

import pytest

from seohead.tools.clusterer import run_clusterer

pytest.importorskip("sklearn", reason="clustering needs the optional cluster extra")


def _clusters(keywords: list[str], k: int) -> int:
    result = run_clusterer(
        {"keywords": keywords, "algorithm": "kmeans", "n_clusters": k, "language": "english"}
    )
    assert result["ok"] is True, result
    return len(result["clusters"])


def test_two_keywords_asked_for_two_clusters_get_two():
    """The boundary the off-by-one hid behind: with the old cap this returned one."""
    assert _clusters(["winter boots", "garden hose"], 2) == 2


def test_asking_for_more_clusters_than_keywords_is_still_capped():
    """The cap itself is right and must stay -- K-Means cannot produce more clusters
    than it has points, and the honest ceiling is the number of keywords, not one less."""
    assert _clusters(["winter boots", "garden hose"], 5) == 2
