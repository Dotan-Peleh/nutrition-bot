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
    "images",
)


def _code_path(code: str) -> str:
    """Insert / every 3 digits (with the last segment holding the remainder).

    OFF stores product images under a sharded path:
        https://images.openfoodfacts.org/images/products/{code_path}/...
    For barcodes >8 chars, split as 3/3/3/rest. Shorter codes stay flat.
    """
    code = (code or "").strip()
    if not code.isdigit() or len(code) <= 8:
        return code
    return f"{code[:3]}/{code[3:6]}/{code[6:9]}/{code[9:]}"


def _image_url(code: str, images: dict | None) -> str | None:
    """Best-effort front image URL at 400px.

    Schema variants seen in 2025 OFF dumps:
      A) {"selected": {"front": {"<lang>": {"rev": "6", "imgid": "1"}}}, ...}
      B) flat {"front_<lang>": {"rev": "12", ...}, "1": {...}, "2": {...}}
    """
    if not code or not images:
        return None
    rev = None
    lang = None
    # Schema A: selected.front.{lang}
    sel_front = (images.get("selected") or {}).get("front") or {}
    if sel_front:
        # Prefer Hebrew, then English, then any.
        for cand in ("he", "en", "fr", *sel_front.keys()):
            if cand in sel_front:
                lang = cand
                rev = sel_front[cand].get("rev")
                break
    # Schema B: flat key "front_<lang>" at top level
    if not rev:
        for cand in ("front_he", "front_en", "front_fr"):
            if cand in images and isinstance(images[cand], dict):
                lang = cand.split("_", 1)[1]
                rev = images[cand].get("rev")
                break
    if not rev:
        return None
    return f"https://images.openfoodfacts.org/images/products/{_code_path(code)}/front_{lang}.{rev}.400.jpg"


def download(dest: Path, *, force: bool = False) -> Path:
    """Download the gzipped JSONL to `dest`. Reuses an existing file unless `force`."""
    if dest.exists() and not force:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", JSONL_URL, timeout=None, follow_redirects=True) as r:
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
        "image_url": _image_url(rec.get("code"), rec.get("images")),
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
