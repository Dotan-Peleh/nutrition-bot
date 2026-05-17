"""Tzameret Israeli food database via the data.gov.il CKAN API.

The direct CSVs are blocked by IAP, but the CKAN `datastore_search` endpoint
is open. We paginate at 1000 rows and stream into a list of dicts; the ETL
orchestrator persists into DuckDB.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

CKAN_BASE = "https://data.gov.il/api/3/action"
PACKAGE_ID = "nutrition-database"

RESOURCE_CACHE_PATH = Path(__file__).parent.parent / "tzameret_resources.json"
PAGE_SIZE = 1000


def _client(timeout: float = 30.0) -> httpx.Client:
    return httpx.Client(timeout=timeout, headers={"User-Agent": "nutricart/0.1"})


def discover_resources(client: httpx.Client | None = None) -> dict[str, str]:
    """Return {resource_name → resource_id} for the Tzameret package, cached."""
    if RESOURCE_CACHE_PATH.exists():
        return json.loads(RESOURCE_CACHE_PATH.read_text())

    own = client is None
    client = client or _client()
    try:
        r = client.get(f"{CKAN_BASE}/package_show", params={"id": PACKAGE_ID})
        r.raise_for_status()
        resources = r.json()["result"]["resources"]
        out = {res["name"]: res["id"] for res in resources}
        RESOURCE_CACHE_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2))
        return out
    finally:
        if own:
            client.close()


def fetch_table(resource_id: str, *, client: httpx.Client | None = None) -> list[dict]:
    """Pull all rows of a single CKAN resource via paginated datastore_search."""
    own = client is None
    client = client or _client()
    try:
        offset = 0
        rows: list[dict] = []
        while True:
            for attempt in range(4):
                try:
                    r = client.get(
                        f"{CKAN_BASE}/datastore_search",
                        params={"resource_id": resource_id, "limit": PAGE_SIZE, "offset": offset},
                    )
                    r.raise_for_status()
                    break
                except httpx.HTTPError:
                    if attempt == 3:
                        raise
                    time.sleep(2 ** attempt)
            page = r.json()["result"]["records"]
            if not page:
                break
            rows.extend(page)
            if len(page) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
        return rows
    finally:
        if own:
            client.close()


def _alias_key(hebrew_name: str) -> str:
    """Map the upstream Hebrew resource title to a stable English key.

    data.gov.il renamed the dataset (tzameret-food-list → nutrition-database) and
    exposes resources under Hebrew titles. We pin the known prefixes to the
    English names the ETL orchestrator expects.
    """
    n = hebrew_name.strip()
    if n.startswith("רשימת המצרכים"):
        return "tzameret_food_list"
    if n.startswith("רשימת המתכונים"):
        return "tzameret_recipes"
    if n.startswith("טבלת יחידות מידה"):
        return "tzameret_units"
    if n.startswith("טבלת משקל"):
        return "tzameret_unit_weights"
    return n


def fetch_all() -> dict[str, list[dict]]:
    """Convenience: pull every Tzameret resource. Slow — use in ETL only."""
    out: dict[str, list[dict]] = {}
    with _client() as client:
        resources = discover_resources(client)
        for name, rid in resources.items():
            key = _alias_key(name)
            out[key] = fetch_table(rid, client=client)
    return out
