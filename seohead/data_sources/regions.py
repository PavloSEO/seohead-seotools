"""Yandex regions for Wordstat and SERP ``regions[]`` parameters.

Regions live in a dedicated module because location is part of a query's meaning, not a minor
request option. The same phrase produces different demand in Moscow and across Russia. Query
different regions with **separate calls**: multiple regions in one request **sum** their volume.
This was verified when ``[213, 2]`` returned 53050 + 20431, the sum of Moscow and Saint
Petersburg, rather than a per-region result.

There are two distinct sources of truth:

* :func:`fetch_tree` uses the authoritative ``getRegionsTree`` endpoint. It is the **only free
  Wordstat method** and should resolve any region absent from the local dictionaries.
* The static dictionaries below provide fast access to frequently used regions. Entries were
  originally verified from documentation or the live API; the verification date is recorded so
  future changes can be checked against the authoritative tree.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RUSSIA = "225"

# Top-level regions and federal districts. Every ID was verified against a live
# ``getRegionsTree`` response containing 1,098 regions on 2026-08-21. Keys intentionally use
# the localized labels returned by the API; substituting administratively official variants can
# break name lookup even when the numeric IDs are correct.
TOP = {
    "Россия": "225",
    "Москва": "213",
    "Москва и область": "1",
    "Санкт-Петербург": "2",
}

DISTRICTS = {
    "Центр": "3",
    "Северо-Запад": "17",
    "Юг": "26",
    "Поволжье": "40",
    "Урал": "52",
    "Сибирь": "59",
    "Дальний Восток": "73",  # 73 is the district; 75 is Vladivostok city.
    "Северный Кавказ": "102444",  # Six digits: this district was created in 2010.
}

# Map official district names to the names returned by the API so both forms resolve.
DISTRICT_ALIASES = {
    "Центральный": "Центр",
    "Северо-Западный": "Северо-Запад",
    "Южный": "Юг",
    "Приволжский": "Поволжье",
    "Уральский": "Урал",
    "Сибирский": "Сибирь",
    "Дальневосточный": "Дальний Восток",
    "Северо-Кавказский": "Северный Кавказ",
}

CITIES = {
    "Екатеринбург": "54",
    "Казань": "43",
    "Новосибирск": "65",
    "Самара": "51",
    "Уфа": "172",
    "Пермь": "50",
    "Краснодар": "35",
    "Ростов-на-Дону": "39",
    "Челябинск": "56",
    "Нижний Новгород": "47",
    "Красноярск": "62",
    "Воронеж": "193",
    "Тюмень": "55",
    "Махачкала": "28",
    "Минеральные Воды": "11063",
    "Калининград": "22",
    "Владивосток": "75",
    "Сочи": "239",
}

# All static IDs matched the live tree on this date.
VERIFIED_AT = "2026-08-21"

ALL_CITY_IDS = list(CITIES.values())
ALL_DISTRICT_IDS = list(DISTRICTS.values())


def by_name(name: str) -> str | None:
    """Resolve a region ID from either an official district name or the API's name.

    Return ``None`` when the name is absent from the static dictionaries; callers can then use
    :func:`fetch_tree` as the authoritative fallback.
    """
    name = DISTRICT_ALIASES.get(name, name)
    for table in (TOP, DISTRICTS, CITIES):
        if name in table:
            return table[name]
    return None


def fetch_tree(save_to: str | None = None) -> dict[str, Any]:
    """Return the complete ``getRegionsTree`` response as ``{name: region_id}``.

    This is the only **free** Wordstat method, so it is intentionally omitted from the spend
    ledger. Traversal recursively inspects every response value because the API's nesting has
    changed over time. Hard-coded key paths broke; this implementation accepts any node with a
    name and an identifier.
    """
    from seohead.data_sources.credentials import MissingCredential
    from seohead.data_sources.yandex_cloud import HOST, Wordstat

    try:
        client = Wordstat()
    except MissingCredential as exc:
        return {"ok": False, "error": str(exc)}

    status, body = client._request(
        f"{HOST}/v2/wordstat/getRegionsTree", {"folderId": client.folder}
    )
    flat: dict[str, str] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            region_id = node.get("id") or node.get("value")
            name = node.get("name") or node.get("label")
            if region_id and name:
                flat[str(name)] = str(region_id)
            for value in node.values():
                if isinstance(value, (dict, list)):
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(body)
    if not flat:
        return {
            "ok": False,
            "error": f"region tree could not be parsed (status {status})",
            "raw": body,
        }

    if save_to:
        path = Path(save_to).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(flat, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "ok": True,
        "count": len(flat),
        "regions": flat,
        "saved_to": str(Path(save_to).expanduser()) if save_to else None,
    }
