"""Regression coverage for DataForSEO keyword-result normalization."""

from __future__ import annotations

import pytest

from seohead.data_sources import dataforseo


@pytest.mark.parametrize(
    ("result_item", "expected_keywords"),
    [
        ({"items": None}, []),
        ({"items": []}, []),
        (
            {
                "items": [
                    {
                        "keyword": "technical seo",
                        "keyword_info": {"search_volume": 100},
                        "keyword_properties": {"keyword_difficulty": 42},
                    },
                    "not a keyword item",
                ]
            },
            [{"phrase": "technical seo", "volume": 100, "difficulty": 42}],
        ),
        (
            {"keyword": "direct result"},
            [{"phrase": "direct result", "volume": None, "difficulty": None}],
        ),
    ],
)
def test_keyword_ideas_distinguishes_empty_items_from_direct_results(
    monkeypatch, result_item, expected_keywords
):
    class FakeClient:
        env = "sandbox"

        def __init__(self, **_kwargs):
            pass

        def post(self, *_args, **_kwargs):
            return {
                "cost": 0,
                "tasks": [{"status_code": 20000, "result": [result_item]}],
            }

    monkeypatch.setattr(dataforseo, "DataForSEOClient", FakeClient)

    response = dataforseo.keyword_ideas("synthetic seed")

    assert response["found"] == len(expected_keywords)
    assert response["keywords"] == expected_keywords
