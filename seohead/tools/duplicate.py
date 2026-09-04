"""Find near-duplicate pages with SimHash and locality-sensitive hashing (LSH).

Large websites often contain tens or hundreds of thin or duplicated pages caused
by faceted pagination, copied content, and utility routes. Comparing every pair
is O(n²): 10,000 pages require roughly 50 million comparisons. SimHash plus LSH
reduces that workload by mapping each page to a 64-bit fingerprint, placing likely
matches in shared bands, and comparing only candidates from a common band.

The implementation uses Charikar's SimHash algorithm:
  1. Text is tokenized into overlapping k-shingles (k=3 by default).
  2. Each shingle is mapped to a deterministic 64-bit FNV-1a hash.
  3. For each bit, the hashes contribute +1 or -1; a positive sum sets that bit in
     the document fingerprint.
  4. Fingerprint similarity is ``1 - (Hamming distance / 64)``.

For candidate retrieval, LSH divides the 64-bit fingerprint into fixed-width
bands. Two documents become candidates when at least one band matches; the exact
Hamming similarity must still meet the configured threshold before they are
joined into a cluster.

Exact duplicates (identical text) are found separately, by hashing each
document's text with SHA-1. A cluster whose members are all exact duplicates
of one another is reported only under ``exact_duplicates``, never under
``clusters`` — otherwise a byte-identical pair would be reported twice, once
as "exact" and once as its own trivial "near" cluster at similarity 1.0.
Hashing the caller-supplied text (rather than raw response bytes) is what
makes the comparison survive a page-unique CSRF token or timestamp: the text
extractor is expected to have already stripped markup and, ideally, scoped
itself to the page's content area (see ``content_area.py``).

Both exact and near comparisons default to indexable pages only — a page
canonicalised to another is an intended twin, not a defect — via the
``indexable`` flag on each item and the ``only_indexable`` parameter.

This module is pure and performs no network access. The caller supplies page text
from a Screaming Frog crawl, live ``parse`` calls, or another audit data source.
Because it is pure, re-running with a new threshold against a stored corpus
costs no requests.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any

# Standard 64-bit FNV-1a constants.
_FNV_OFFSET = 0xCBF29CE484222325
_FNV_PRIME = 0x100000001B3
_MASK64 = (1 << 64) - 1

# LSH uses 16 bands of 4 bits each. A match in one 4-bit band creates a
# candidate pair, balancing recall against the number of false candidates.
_BANDS = 16
_BAND_BITS = 4
_DEFAULT_THRESHOLD = 0.92  # 1 - 5/64 ~= 0.922; lower similarity is not a match


def _tokenize(text: str) -> list[str]:
    """Return lowercase alphanumeric tokens with at least two characters.

    Punctuation and HTML entities are discarded. The tokenizer is language
    independent because Python's Unicode-aware ``\\w`` also covers Cyrillic.
    """
    if not text:
        return []
    return [t for t in re.findall(r"\w{2,}", text.lower(), flags=re.UNICODE) if len(t) >= 2]


def shingles(tokens: list[str], k: int = 3) -> list[tuple[str, ...]]:
    """Return overlapping k-shingles, or one shingle when fewer than k tokens exist."""
    if not tokens:
        return []
    if len(tokens) <= k:
        return [tuple(tokens)]
    return [tuple(tokens[i : i + k]) for i in range(len(tokens) - k + 1)]


def fnv1a_64(data: str) -> int:
    """Return a deterministic, dependency-free 64-bit FNV-1a string hash."""
    h = _FNV_OFFSET
    for byte in data.encode("utf-8"):
        h ^= byte
        h = (h * _FNV_PRIME) & _MASK64
    return h


def simhash(text: str, k: int = 3) -> int:
    """Return a 64-bit SimHash fingerprint; identical texts produce the same hash."""
    toks = _tokenize(text)
    sh = shingles(toks, k)
    if not sh:
        return 0
    # Accumulate each bit's +1/-1 vote across all shingle hashes.
    v = [0] * 64
    for piece in sh:
        h = fnv1a_64(" ".join(piece))
        for i in range(64):
            v[i] += 1 if (h >> i) & 1 else -1
    fp = 0
    for i in range(64):
        if v[i] > 0:
            fp |= 1 << i
    return fp


def hamming(a: int, b: int) -> int:
    """Return the Hamming distance between two 64-bit fingerprints."""
    return (a ^ b).bit_count()


def similarity(a: int, b: int) -> float:
    """Return similarity in [0, 1] as ``1 - Hamming distance / 64``."""
    return 1.0 - hamming(a, b) / 64.0


def content_hash(text: str) -> str:
    """Return a SHA-1 hex digest of ``text``, for exact-duplicate grouping.

    Hashing the extracted text rather than raw response bytes means a
    per-request CSRF token or timestamp embedded elsewhere in the markup does
    not defeat the comparison.
    """
    return hashlib.sha1((text or "").encode("utf-8"), usedforsecurity=False).hexdigest()


def _band_keys(fp: int, bands: int = _BANDS, band_bits: int = _BAND_BITS) -> list[int]:
    """Return the fingerprint value for each LSH band as its bucket key."""
    keys: list[int] = []
    mask = (1 << band_bits) - 1
    for i in range(bands):
        keys.append((fp >> (i * band_bits)) & mask)
    return keys


def find_duplicates(
    items: list[dict[str, Any]],
    threshold: float = _DEFAULT_THRESHOLD,
    k: int = 3,
    with_fingerprints: bool = False,
    only_indexable: bool = True,
) -> dict[str, Any]:
    """Find exact and near-duplicate groups in a list of documents.

    Each item is ``{"id": str, "text": str}``, where ``id`` may be a URL or
    any stable key, plus an optional ``indexable`` flag (default True). Near
    duplicates are groups whose exact similarity is at least ``threshold``;
    LSH retrieves candidates without an all-pairs scan, while the reported
    pair values are calculated with exact Hamming similarity.

    ``only_indexable`` (default True) drops non-indexable items before either
    comparison: a page canonicalised to another is an intended twin, not a
    defect. Set it to False to audit the canonical tags themselves.

    ``with_fingerprints`` includes each document fingerprint. It is disabled by
    default because the mapping can dominate output for hundreds of pages and is
    mainly useful for debugging fingerprint behavior.
    """
    excluded_non_indexable = 0
    if only_indexable:
        kept = [it for it in items if it.get("indexable", True)]
        excluded_non_indexable = len(items) - len(kept)
        items = kept

    if not items:
        out: dict[str, Any] = {
            "ok": True,
            "count": 0,
            "clusters": [],
            "exact_duplicates": [],
            "excluded_non_indexable": excluded_non_indexable,
        }
        if with_fingerprints:
            out["fingerprints"] = {}
        return out

    fingerprints: dict[str, int] = {}
    texts: dict[str, str] = {}
    for it in items:
        doc_id = it.get("id") or it.get("url") or ""
        text = it.get("text") or ""
        if doc_id:
            fingerprints[str(doc_id)] = simhash(text, k=k)
            texts[str(doc_id)] = text

    # Exact groups are found by content hash, independent of the near-duplicate
    # pass below, so they are unaffected by threshold or LSH banding.
    hash_groups: dict[str, list[str]] = defaultdict(list)
    for doc_id, text in texts.items():
        hash_groups[content_hash(text)].append(doc_id)
    exact_duplicates = [
        {"hash": h, "members": sorted(members)}
        for h, members in hash_groups.items()
        if len(members) > 1
    ]
    exact_duplicates.sort(key=lambda g: g["hash"])
    hash_of: dict[str, str] = {
        doc_id: h for h, members in hash_groups.items() for doc_id in members
    }

    # LSH buckets candidates by each fingerprint band.
    buckets: dict[tuple[int, int], list[str]] = defaultdict(list)
    for doc_id, fp in fingerprints.items():
        for band_idx, key in enumerate(_band_keys(fp)):
            buckets[(band_idx, key)].append(doc_id)

    # Union-find converts matching candidate pairs into transitive clusters.
    parent: dict[str, str] = {doc_id: doc_id for doc_id in fingerprints}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    candidate_pairs: set[tuple[str, str]] = set()
    for members in buckets.values():
        if len(members) < 2:
            continue
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = members[i], members[j]
                if similarity(fingerprints[a], fingerprints[b]) >= threshold:
                    candidate_pairs.add(tuple(sorted((a, b))))
                    union(a, b)

    # Group documents by their union-find root.
    groups: dict[str, list[str]] = defaultdict(list)
    for doc_id in fingerprints:
        groups[find(doc_id)].append(doc_id)

    clusters: list[dict[str, Any]] = []
    for members in groups.values():
        if len(members) < 2:
            continue  # A singleton cannot be a duplicate cluster.
        # A cluster where every member shares the same content hash is fully
        # explained by exact duplication and already listed in
        # exact_duplicates; reporting it again here would double-report it.
        if len({hash_of[m] for m in members}) == 1:
            continue
        # Calculate all pair similarities inside each cluster for reporting.
        pairs = []
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = members[i], members[j]
                pairs.append(
                    {
                        "a": a,
                        "b": b,
                        "similarity": round(similarity(fingerprints[a], fingerprints[b]), 4),
                    }
                )
        clusters.append(
            {
                "members": members,
                "pairs": pairs,
                "min_similarity": min(p["similarity"] for p in pairs),
            }
        )

    clusters.sort(key=lambda c: -c["min_similarity"])
    result: dict[str, Any] = {
        "ok": True,
        "count": len(fingerprints),
        "threshold": threshold,
        "clusters": clusters,
        "exact_duplicates": exact_duplicates,
        "candidate_pairs_checked": len(candidate_pairs),
        "excluded_non_indexable": excluded_non_indexable,
    }
    if with_fingerprints:
        result["fingerprints"] = fingerprints
    return result
