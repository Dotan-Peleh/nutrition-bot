"""Open Food Facts — Israeli subset.

Streams the country-filtered JSONL dump and yields records of interest.
We avoid loading the full 1+ GB dump into memory by streaming line-by-line.
"""
from __future__ import annotations

import gzip
import json
from collections.abc import Iterable, Iterator
from pathlib import Path

import httpx

JSONL_URL = "https://static.openfoodfacts.org/data/openfoodfacts-products.jsonl.gz"
FIELDS = (
    "code", "product_name", "product_name_he", "brands", "categories_tags",
    "countries_tags", "nutriments", "nutriscore_grade", "nova_group", "serving_size",
)


def download(dest: Path, *, force: bool = False) -> Path:
    """Download the gzipped JSONL to `dest`. Reuses an existing file unless `force`."""
    if dest.exists() and not force:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", JSONL_URL, timeout=None) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    return dest


def iter_israeli(path: Path) -> Iterator[dict]:
    """Stream the dump, yielding only IL products with the fields we need."""
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            countries = rec.get("countries_tags") or []
            if "en:israel" not in countries:
                continue
            yield {k: rec.get(k) for k in FIELDS}


def to_nutricart_record(rec: dict) -> dict:
    """Map an OFF record to a flat dict compatible with our `products` table."""
    nutriments = rec.get("nutriments") or {}
    return {
        "source": "off",
        "source_id": rec.get("code") or "",
        "name_he": rec.get("product_name_he") or rec.get("product_name") or "",
        "name_en": rec.get("product_name") or None,
        "brand": (rec.get("brands") or "").split(",")[0].strip() or None,
        "barcode": rec.get("code") or None,
        "serving_size_g": _parse_serving(rec.get("serving_size")),
        "nutriscore_grade": rec.get("nutriscore_grade"),
        "categories_tags": rec.get("categories_tags") or [],
        "nutrients": {
            "energy_kj":  float(nutriments.get("energy-kj_100g") or 0),
            "sat_fat_g":  float(nutriments.get("saturated-fat_100g") or 0),
            "sugars_g":   float(nutriments.get("sugars_100g") or 0),
            "sodium_mg":  float(nutriments.get("sodium_100g") or 0) * 1000,
            "fiber_g":    float(nutriments.get("fiber_100g") or 0),
            "protein_g":  float(nutriments.get("proteins_100g") or 0),
            "fvl_pct":    float(nutriments.get("fruits-vegetables-legumes_estimate_from_ingredients_100g") or 0),
        },
    }


def _parse_serving(s) -> float | None:
    if not s:
        return None
    import re
    m = re.search(r"(\d+(?:\.\d+)?)\s*g", str(s))
    return float(m.group(1)) if m else None


def collect(path: Path, limit: int | None = None) -> Iterable[dict]:
    """Eager iterator (for ETL convenience)."""
    out: list[dict] = []
    for i, rec in enumerate(iter_israeli(path)):
        out.append(to_nutricart_record(rec))
        if limit and i + 1 >= limit:
            break
    return out
