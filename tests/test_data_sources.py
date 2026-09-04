"""Offline tests for external data-source behavior around the API calls."""

from __future__ import annotations

import json

import pytest

from seohead.data_sources import arsenkin, credentials, spend, yandex_cloud

# --- Credentials -----------------------------------------------------------


def test_credential_from_env_wins(monkeypatch):
    monkeypatch.setenv("SOME_TOKEN", "  from-environment  ")
    assert credentials.read("missing/path", "SOME_TOKEN") == "from-environment"


def test_credential_missing_names_path_but_not_value(monkeypatch, tmp_path):
    monkeypatch.delenv("SOME_TOKEN", raising=False)
    monkeypatch.setattr(credentials, "CONFIG_ROOT", tmp_path)
    with pytest.raises(credentials.MissingCredential) as exc:
        credentials.read("svc/token", "SOME_TOKEN")
    message = str(exc.value)
    assert "svc/token" in message and "SOME_TOKEN" in message


def test_credential_empty_file_is_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("SOME_TOKEN", raising=False)
    monkeypatch.setattr(credentials, "CONFIG_ROOT", tmp_path)
    (tmp_path / "svc").mkdir()
    (tmp_path / "svc" / "token").write_text("   \n", encoding="utf-8")
    with pytest.raises(credentials.MissingCredential):
        credentials.read("svc/token", "SOME_TOKEN")


def test_available_is_false_without_secret(monkeypatch, tmp_path):
    monkeypatch.delenv("NOPE", raising=False)
    monkeypatch.setattr(credentials, "CONFIG_ROOT", tmp_path)
    assert credentials.available("nope/token", "NOPE") is False


# --- Spend journal ---------------------------------------------------------


@pytest.fixture()
def journal(monkeypatch, tmp_path):
    monkeypatch.setenv("SEOHEAD_SPEND_LOG", str(tmp_path / "spend.jsonl"))
    return tmp_path / "spend.jsonl"


def test_spend_records_and_sums_by_unit(journal):
    spend.record("arsenkin", "keyword_exact", cost=120, unit="limits", task_id=555, items=40)
    spend.record("arsenkin", "keyword_exact", cost=30, unit="limits", task_id=556, items=10)
    spend.record("yandex_cloud", "wordstat.topRequests", cost=1, unit="requests", items=1)

    report = spend.report()
    assert report["calls"] == 3
    assert report["by_source"]["arsenkin"]["limits"] == 150.0
    assert report["by_source"]["yandex_cloud"]["requests"] == 1.0
    assert report["by_operation"]["arsenkin.keyword_exact"]["limits"] == 150.0


def test_spend_keeps_task_ids_so_paid_results_can_be_refetched(journal):
    spend.record("arsenkin", "top", cost=10, task_id=1)
    spend.record("arsenkin", "top", cost=10, task_id=2)
    spend.record("yandex_cloud", "serp", cost=1)  # No task ID is available.
    assert spend.paid_task_ids("arsenkin") == [1, 2]
    assert spend.paid_task_ids("yandex_cloud") == []


def test_spend_survives_broken_line(journal):
    spend.record("arsenkin", "top", cost=5)
    with journal.open("a", encoding="utf-8") as handle:
        handle.write("this is not JSON\n")
    spend.record("arsenkin", "top", cost=5)
    assert spend.report()["calls"] == 2  # The malformed line is skipped without breaking the log.


def test_spend_report_since_filters_by_day(journal, monkeypatch):
    spend.record("arsenkin", "top", cost=5)
    rows = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    old = dict(rows[0], at="2020-01-01T00:00:00")
    with journal.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(old, ensure_ascii=False) + "\n")
    assert spend.report()["calls"] == 1
    assert spend.report(since="2026-01-01")["calls"] == 0


def test_spend_report_on_missing_log_is_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("SEOHEAD_SPEND_LOG", str(tmp_path / "missing.jsonl"))
    report = spend.report()
    assert report["calls"] == 0 and report["by_source"] == {}


# --- Arsenkin rate limiting and usage accounting --------------------------


def test_rate_limiter_keeps_headroom_under_the_wall():
    limiter = arsenkin.RateLimiter(max_calls=30, period=60.0, safety=3)
    assert limiter.max_calls == 27  # Headroom prevents bursts of HTTP 429 responses.


def test_rate_limiter_never_drops_below_one():
    assert arsenkin.RateLimiter(max_calls=2, safety=10).max_calls == 1


@pytest.mark.parametrize(
    "data,expected",
    [
        ({"keywords": ["alpha", "beta", "gamma"]}, 3),
        ({"words": "alpha\nbeta\n\ngamma\n"}, 3),
        ({"urls": []}, 0),
        ({"unrelated": "value"}, 0),
    ],
)
def test_count_items_for_journal(data, expected):
    assert arsenkin._count_items(data) == expected


def test_refetch_is_get_so_paid_result_is_not_bought_twice():
    assert arsenkin.ArsenkinClient.refetch is arsenkin.ArsenkinClient.get


# --- Yandex Cloud normalization and SERP parsing --------------------------


# Cyrillic fixtures intentionally verify Russian case folding and yo-character normalization.
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("  Тёплый   ПОЛ ", "теплый пол"),
        ("ЁЛКА", "елка"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize(raw, expected):
    assert yandex_cloud.normalize(raw) == expected


def test_parse_serp_extracts_position_url_domain_title():
    xml = (
        "<doc><url>https://www.example.com/a</url><title>First result</title></doc>"
        "<doc><url>https://search.example/x</url><domain>search.example</domain>"
        "<title>Second result</title></doc>"
    )
    docs = yandex_cloud.parse_serp(xml)
    assert [d["pos"] for d in docs] == [1, 2]
    assert docs[0]["domain"] == "example.com"  # The ``www`` prefix is removed.
    assert docs[0]["title"] == "First result"
    assert docs[1]["domain"] == "search.example"


def test_parse_serp_strips_highlight_tags_inside_title():
    xml = (
        "<doc><url>https://search.example/</url><title>buy<hlword>ing</hlword> a pump</title></doc>"
    )
    assert yandex_cloud.parse_serp(xml)[0]["title"] == "buying a pump"


def test_parse_serp_on_empty_input_is_empty_not_error():
    assert yandex_cloud.parse_serp("") == []


def test_serp_body_never_asks_for_sync_search():
    """Synchronous search is deliberately absent because it costs 16 times more."""
    # The Cyrillic query intentionally exercises the Russian Yandex search type.
    body = yandex_cloud._serp_body(
        "тест", "225", "SEARCH_TYPE_RU", 10, 1, "FAMILY_MODE_NONE", "folder-1"
    )
    assert body["responseFormat"] == "FORMAT_XML"
    assert body["query"]["queryText"] == "тест"
    assert not hasattr(yandex_cloud.WebSearch, "search_sync")


# --- Regions ---------------------------------------------------------------

# Cyrillic region names intentionally verify Yandex's Russian aliases and canonical names.


def test_region_lookup_understands_both_official_and_api_names():
    """The official and API-specific names resolve to the same federal district."""
    from seohead.data_sources import yandex_regions as regions

    assert regions.by_name("Поволжье") == "40"
    assert regions.by_name("Приволжский") == "40"
    assert regions.by_name("Дальневосточный") == regions.by_name("Дальний Восток") == "73"


def test_region_lookup_returns_none_for_unknown():
    from seohead.data_sources import yandex_regions as regions

    assert regions.by_name("Atlantis") is None


def test_vladivostok_city_is_not_the_district():
    """Code 75 is the city and 73 the district; mixing them distorts demand data."""
    from seohead.data_sources import yandex_regions as regions

    assert regions.CITIES["Владивосток"] == "75"
    assert regions.DISTRICTS["Дальний Восток"] == "73"


def test_every_district_alias_points_at_a_real_district():
    from seohead.data_sources import yandex_regions as regions

    assert all(target in regions.DISTRICTS for target in regions.DISTRICT_ALIASES.values())


# --- Yandex Metrica --------------------------------------------------------


def test_metrika_backoff_respects_retry_after_header():
    """A valid Retry-After value takes precedence over the local backoff formula."""
    from seohead.data_sources.metrika import MetrikaClient

    assert MetrikaClient._backoff(1, "5") == 5.0
    assert MetrikaClient._backoff(1, "600") == 60.0  # Never wait longer than one minute.
    assert MetrikaClient._backoff(3, None) == 4.0  # Fall back to exponential backoff.
    assert MetrikaClient._backoff(1, "not-a-number") == 1.0  # Ignore invalid headers.


def test_metrika_backoff_is_capped():
    from seohead.data_sources.metrika import MAX_BACKOFF, MetrikaClient

    assert MetrikaClient._backoff(20, None) == MAX_BACKOFF


@pytest.mark.parametrize(
    "payload,expected",
    [
        ('{"message": "Counter not found"}', "Counter not found"),
        ('{"errors": [{"message": "Invalid metric"}]}', "Invalid metric"),
        ('{"errors": ["Flat error string"]}', "Flat error string"),
        ("not JSON at all", "not JSON at all"),
        ("", "empty response"),
    ],
)
def test_metrika_error_message_is_extracted_from_api_answer(payload, expected):
    from seohead.data_sources.metrika import _api_message

    assert _api_message(payload) == expected


def test_metrika_error_carries_status():
    from seohead.data_sources.metrika import MetrikaError

    exc = MetrikaError(429, "Too many requests")
    assert exc.status == 429 and "429" in str(exc)


def test_metrika_url_drops_empty_params_but_keeps_zero():
    from seohead.data_sources.metrika import MetrikaClient

    url = MetrikaClient._url(
        "stat/v1/data", {"limit": 100, "offset": 0, "filters": "", "preset": None}
    )
    assert "limit=100" in url and "offset=0" in url
    assert "filters" not in url and "preset" not in url


def test_metrika_rows_to_records_pairs_dimensions_with_metrics():
    """Pair Metrica's parallel dimension and metric arrays without shifting columns."""
    from seohead.data_sources.metrika import rows_to_records

    report = {
        "query": {"dimensions": ["ym:s:startURL"], "metrics": ["ym:s:visits", "ym:s:users"]},
        "data": [
            {"dimensions": [{"name": "/blog"}], "metrics": [120, 90]},
            {"dimensions": [{"name": "/about"}], "metrics": [10, 8]},
        ],
    }
    assert rows_to_records(report) == [
        {"startURL": "/blog", "visits": 120, "users": 90},
        {"startURL": "/about", "visits": 10, "users": 8},
    ]


def test_metrika_rows_to_records_survives_missing_query_and_extra_columns():
    from seohead.data_sources.metrika import rows_to_records

    report = {"data": [{"dimensions": ["plain string"], "metrics": [1]}]}
    assert rows_to_records(report) == [{"dimension_0": "plain string", "metric_0": 1}]
    assert rows_to_records({}) == []


def test_metrika_row_cap_exists_so_a_typo_cannot_pull_a_million_rows():
    from seohead.data_sources import metrika

    assert metrika.ROW_CAP == 100_000
    assert metrika.PAGE_PAUSE > 0  # Paging without a pause can exhaust the request quota.


# --- Arsenkin task batches -------------------------------------------------


class _FakeClient:
    """Offline client double with controllable submission and polling failures."""

    def __init__(self, fail_on=(), fail_wait_on=()):
        self.fail_on, self.fail_wait_on = set(fail_on), set(fail_wait_on)
        self.set_calls = []

    def set_task(self, tools_name, data):
        label = data.get("label")
        self.set_calls.append(label)
        if label in self.fail_on:
            raise arsenkin.ArsenkinError("400", f"invalid task {label}")
        return {"task_id": 1000 + len(self.set_calls), "cost": 10, "raw": {}}

    def wait(self, task_id, **kwargs):
        if task_id in self.fail_wait_on:
            raise arsenkin.ArsenkinError("TIMEOUT", f"task {task_id} timed out")
        return {"result": {"task": task_id}}

    def get(self, task_id):
        return {"result": {"refetched": task_id}}


def _jobs(*labels):
    return [
        {"tools_name": "wordstat", "data": {"label": label}, "label": label} for label in labels
    ]


def test_batch_keeps_input_order():
    runner = arsenkin.BatchRunner(client=_FakeClient())
    results = runner.run(_jobs("alpha", "beta", "gamma", "delta"))
    assert [r["label"] for r in results] == ["alpha", "beta", "gamma", "delta"]


def test_batch_one_bad_job_does_not_kill_the_rest():
    """A mid-batch exception must not orphan results from already paid tasks."""
    runner = arsenkin.BatchRunner(client=_FakeClient(fail_on={"beta"}))
    results = runner.run(_jobs("alpha", "beta", "gamma"))
    assert "error" in results[1] and results[1]["code"] == "400"
    assert "result" in results[0] and "result" in results[2]


def test_batch_failed_wait_still_returns_task_id_because_it_is_paid():
    client = _FakeClient(fail_wait_on={1001})
    results = arsenkin.BatchRunner(client=client).run(_jobs("one"))
    assert results[0]["task_id"] == 1001  # Return the identifier for the paid task.
    assert results[0]["cost"] == 10
    assert "error" in results[0]


def test_batch_respects_the_five_task_api_ceiling():
    from seohead.data_sources.arsenkin import MAX_CONCURRENT

    assert MAX_CONCURRENT == 5
    runner = arsenkin.BatchRunner(client=_FakeClient())
    assert runner._max_concurrent == 5


def test_batch_refetch_is_free_and_goes_through_get():
    client = _FakeClient()
    assert arsenkin.BatchRunner(client=client).refetch(777) == {"result": {"refetched": 777}}


def test_batch_on_empty_list_is_empty():
    assert arsenkin.BatchRunner(client=_FakeClient()).run([]) == []


# --- DataForSEO: Google ----------------------------------------------------


@pytest.mark.parametrize(
    "country", ["RU", "ru", "Россия", "россия", "РФ", "Russia", "BY", "Беларусь", "belarus"]
)
def test_geo_guard_blocks_geos_dataforseo_does_not_have(country):
    """Block unsupported geographies before a paid request returns no data."""
    # Cyrillic aliases intentionally verify localized Russia and Belarus inputs.
    from seohead.data_sources.dataforseo import geo_guard

    blocked = geo_guard(country)
    assert blocked is not None
    assert blocked["ok"] is False
    assert blocked["unsupported_geo"] in {"RU", "BY"}
    assert blocked["use_instead"]  # Always recommend the appropriate alternative provider.


@pytest.mark.parametrize("country", ["US", "de", "India", None, ""])
def test_geo_guard_lets_supported_geo_through(country):
    from seohead.data_sources.dataforseo import geo_guard

    assert geo_guard(country) is None


def test_default_environment_is_sandbox_so_nothing_is_charged_by_accident(monkeypatch):
    monkeypatch.delenv("DATAFORSEO_ENV", raising=False)
    from seohead.data_sources.dataforseo import SANDBOX_BASE, DataForSEOClient

    client = DataForSEOClient()
    assert client.env == "sandbox" and client.base == SANDBOX_BASE


def test_prod_requires_an_explicit_switch(monkeypatch):
    from seohead.data_sources.dataforseo import PROD_BASE, DataForSEOClient

    monkeypatch.setenv("DATAFORSEO_ENV", "prod")
    assert DataForSEOClient().base == PROD_BASE
    monkeypatch.delenv("DATAFORSEO_ENV")
    assert DataForSEOClient(env="prod").base == PROD_BASE


def test_task_items_survives_none_at_every_nesting_level():
    """Handle ``None`` at every level of the nested task-result-item response."""
    from seohead.data_sources.dataforseo import task_items

    assert task_items({}) == []
    assert task_items({"tasks": None}) == []
    assert task_items({"tasks": [{"result": None}]}) == []
    assert task_items({"tasks": [{"result": [{"items": None}]}]}) == [{"items": None}]
    assert task_items({"tasks": [{"result": [{"items": [{"keyword": "alpha"}]}]}]}) == [
        {"keyword": "alpha"}
    ]


def test_task_items_merges_several_tasks():
    from seohead.data_sources.dataforseo import task_items

    body = {
        "tasks": [
            {"result": [{"items": [{"keyword": "alpha"}, {"keyword": "beta"}]}]},
            {"result": [{"items": [{"keyword": "gamma"}]}]},
        ]
    }
    assert [i["keyword"] for i in task_items(body)] == ["alpha", "beta", "gamma"]


def test_task_errors_reports_everything_except_success_code():
    from seohead.data_sources.dataforseo import task_errors

    body = {
        "tasks": [
            {"status_code": 20000, "status_message": "Ok."},
            {"status_code": 40501, "status_message": "Invalid Field: 'location_code'"},
        ]
    }
    errors = task_errors(body)
    assert len(errors) == 1 and "40501" in errors[0]


def test_endpoints_are_v3_and_live_where_expected():
    from seohead.data_sources.dataforseo import ENDPOINTS

    assert all(path.startswith("v3/") for path in ENDPOINTS.values())
    assert "live" in ENDPOINTS["search_volume"]


def test_error_message_comes_from_the_api_not_from_us():
    from seohead.data_sources.dataforseo import _message

    assert _message('{"status_message": "Payment Required."}') == "Payment Required."
    assert _message('{"tasks":[{"status_message":"Invalid Field"}]}') == "Invalid Field"
    assert _message("") == "empty response"


# --- CLI list parsing ------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("alpha,beta,gamma", ["alpha", "beta", "gamma"]),
        ("  alpha , beta ", ["alpha", "beta"]),
        ("single", ["single"]),
        ("", None),
        (None, None),
        ("alpha,,beta", ["alpha", "beta"]),
    ],
)
def test_split_list_plain(raw, expected):
    from seohead.cli import _split_list

    assert _split_list(raw) == expected


def test_split_list_keeps_comma_inside_quotes():
    """A quoted comma must not split one query into two paid requests."""
    from seohead.cli import _split_list

    assert _split_list("'CDM pumps — specifications, selection, and prices'") == [
        "CDM pumps — specifications, selection, and prices"
    ]
    assert _split_list("'first, with a comma','second'") == ["first, with a comma", "second"]
    assert _split_list('"alpha, beta",gamma') == ["alpha, beta", "gamma"]
