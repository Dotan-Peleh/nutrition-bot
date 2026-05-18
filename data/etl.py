"""ETL orchestrator: builds nutricart.duckdb from all three sources.

Idempotent — re-runs blow away the DB and recreate it. Use a staging directory
for the OFF dump (~1 GB) and the transparency XMLs.

Run: `python -m data.etl` (uses `NUTRICART_DB_PATH` env var if set).
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from collections.abc import Iterable
from pathlib import Path

import duckdb
from rapidfuzz import fuzz

from data.db import connect, init_schema, reset
from data.sources import off, transparency, tzameret
from data.taxonomy import TAXONOMY

LOG = logging.getLogger("etl")
RAW_DIR = Path(__file__).parent / "raw"


def _canonical_id(source: str, source_id: str) -> str:
    h = hashlib.sha1(f"{source}:{source_id}".encode()).hexdigest()[:16]
    return f"{source}_{h}"


def _seed_taxonomy(con: duckdb.DuckDBPyConnection) -> None:
    con.executemany(
        "INSERT INTO categories VALUES (?, ?, ?, ?, ?)",
        [(c.category_id, c.parent_id, c.name_he, c.name_en, c.kind) for c in TAXONOMY],
    )


def _insert_product(con: duckdb.DuckDBPyConnection, rec: dict) -> str:
    cid = _canonical_id(rec["source"], rec["source_id"])
    con.execute(
        "INSERT OR IGNORE INTO products "
        "(canonical_id, name_he, name_en, brand, category_id, barcode, "
        " source, source_id, serving_size_g, available_in_il, data_quality, "
        " image_url, price_ils, price_per_100g_ils) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            cid,
            rec.get("name_he") or "",
            rec.get("name_en"),
            rec.get("brand"),
            rec.get("category_id"),
            rec.get("barcode"),
            rec["source"],
            rec["source_id"],
            rec.get("serving_size_g"),
            bool(rec.get("available_in_il", False)),
            rec.get("data_quality", "ok"),
            rec.get("image_url"),
            rec.get("price_ils"),
            rec.get("price_per_100g_ils"),
        ],
    )
    for code, value in (rec.get("nutrients") or {}).items():
        if value is None:
            continue
        con.execute(
            "INSERT OR IGNORE INTO nutrients VALUES (?, ?, ?, ?)",
            [cid, code, float(value), None],
        )
    return cid


_TZAMERET_2DIGIT = {
    # Dairy
    "11": "milk", "12": "milk", "13": "soft_cheese", "14": "yogurt",
    # Meat / fish / eggs (group 2x)
    "21": "meat_fish", "22": "meat_fish", "23": "meat_fish",
    "24": "meat_fish", "25": "meat_fish", "26": "meat_fish",
    "27": "meat_fish", "28": "meat_fish",
    # Eggs / legumes / nuts (3x, 4x)
    "31": "pantry", "41": "pantry", "42": "pantry", "43": "pantry", "44": "pantry",
    # Grains / bread / pasta (5x)
    "50": "bakery", "51": "bakery", "52": "bakery", "53": "bakery",
    "54": "bakery", "55": "bakery", "56": "bakery", "57": "breakfast",
    # Fruits, vegetables (6x, 7x)
    "61": "produce", "62": "produce", "63": "produce", "64": "produce",
    "71": "produce", "72": "produce", "73": "produce", "74": "produce", "75": "produce",
    # Fats and oils (8x)
    "81": "pantry", "82": "pantry", "83": "pantry",
    # Sweets, sugars, beverages (9x)
    "91": "sweets", "92": "sweets", "93": "beverages", "94": "beverages",
}


def _map_tzameret_category(source_id: str, name_he: str) -> str | None:
    """Map Tzameret smlmitzrach prefix + name keywords to taxonomy category_id."""
    name = (name_he or "").lower()
    # Name-based overrides for distinct sub-categories first.
    # IMPORTANT: keywords must be context-anchored — bare adjectives like "צהוב"
    # (yellow) match yellow peppers/peaches/etc. and silently corrupt categories.
    if "קוטג" in name:
        return "cottage"
    if "במבה" in name or "ביסלי" in name or "חטיף" in name or "פופקורן" in name:
        return "snacks"
    if "גבינה צהובה" in name or "גבינה קשה" in name or "אמנטל" in name or "צ'דר" in name:
        return "hard_cheese"
    if "חמאה" in name and "בוטנים" not in name:
        return "butter"
    if "שמנת" in name:
        return "cream"
    code = (source_id or "").lstrip()
    if len(code) >= 2:
        cat = _TZAMERET_2DIGIT.get(code[:2])
        if cat:
            return cat
    return None


def _load_tzameret(con: duckdb.DuckDBPyConnection) -> int:
    LOG.info("fetching Tzameret …")
    tables = tzameret.fetch_all()
    food_list = tables.get("tzameret_food_list", [])
    inserted = 0
    for row in food_list:
        source_id = str(row.get("smlmitzrach") or row.get("food_code") or row.get("_id") or "")
        name_he = row.get("shmmitzrach") or row.get("name_he") or ""
        rec = {
            "source": "tzameret",
            "source_id": source_id,
            "name_he": name_he,
            "name_en": row.get("english_name"),
            "category_id": _map_tzameret_category(source_id, name_he),
            "available_in_il": True,  # Tzameret is the Israeli MoH catalog
            "serving_size_g": _coerce_float(row.get("portion_size_g")),
            "nutrients": {
                "energy_kj":  _coerce_float(row.get("energy_kj")),
                "sat_fat_g":  _coerce_float(row.get("saturated_fat")),
                "sugars_g":   _coerce_float(row.get("total_sugars")),
                "sodium_mg":  _coerce_float(row.get("sodium")),
                "fiber_g":    _coerce_float(row.get("total_dietary_fiber")),
                "protein_g":  _coerce_float(row.get("protein")),
            },
        }
        if not rec["source_id"]:
            continue
        _insert_product(con, rec)
        inserted += 1
    LOG.info("Tzameret: %d products", inserted)
    return inserted


def _load_off(con: duckdb.DuckDBPyConnection, limit: int | None = None) -> int:
    LOG.info("downloading OFF dump (if needed) …")
    dump = off.download(RAW_DIR / "off.jsonl.gz")
    inserted = 0
    for rec in off.collect(dump, limit=limit):
        # OFF.iter_israeli() already filters by country=Israel, so flip the flag.
        rec.setdefault("category_id", _map_off_category(rec))
        _insert_product(con, rec | {"available_in_il": True})
        inserted += 1
        if inserted % 5000 == 0:
            LOG.info("OFF: %d products inserted so far", inserted)
    LOG.info("OFF: %d Israeli products", inserted)
    return inserted


def _map_off_category(rec: dict) -> str | None:
    """Map OFF categories_tags + name keywords to our 48-leaf taxonomy.

    OFF tags look like 'en:dairies', 'en:cheeses', 'en:yogurts', etc. We use a
    coarse prefix lookup; the name-based overrides from _map_tzameret_category
    are reused for finer cuts.
    """
    name_he = rec.get("name_he") or rec.get("name_en") or ""
    tagged = _map_tzameret_category("", name_he)
    if tagged:
        return tagged
    tags = " ".join(rec.get("categories_tags") or []).lower()
    if "yogurt" in tags: return "yogurt"
    if "cheese" in tags: return "soft_cheese"
    if "milk" in tags: return "milk"
    if "bread" in tags or "bakery" in tags: return "bakery"
    if "cereal" in tags or "breakfast" in tags: return "breakfast"
    if "snack" in tags or "chips" in tags: return "snacks"
    if "soft-drink" in tags or "beverage" in tags or "soda" in tags: return "beverages"
    if "fruit" in tags or "vegetable" in tags or "produce" in tags: return "produce"
    if "meat" in tags or "fish" in tags or "seafood" in tags: return "meat_fish"
    if "sweet" in tags or "candy" in tags or "chocolate" in tags: return "sweets"
    if "frozen" in tags: return "frozen"
    return "pantry"


def _load_transparency(con: duckdb.DuckDBPyConnection) -> int:
    LOG.info("fetching transparency XMLs …")
    try:
        rows = transparency.collect(RAW_DIR / "transparency")
    except Exception as e:  # noqa: BLE001
        LOG.warning("transparency fetch failed: %s", e)
        return 0

    for row in rows:
        existing = con.execute(
            "SELECT canonical_id FROM products WHERE barcode = ? LIMIT 1",
            [row["barcode"]],
        ).fetchone()
        if existing:
            # Update existing product (likely an OFF row) with IL availability + price.
            con.execute(
                "UPDATE products SET available_in_il = TRUE, "
                "price_ils = COALESCE(?, price_ils), "
                "price_per_100g_ils = COALESCE(?, price_per_100g_ils), "
                "brand = COALESCE(brand, ?) "
                "WHERE canonical_id = ?",
                [row.get("price_ils"), row.get("price_per_100g_ils"),
                 row.get("brand"), existing[0]],
            )
        else:
            rec = {
                "source": "transparency",
                "source_id": row["barcode"],
                "name_he": row["name_he"],
                "brand": row["brand"],
                "barcode": row["barcode"],
                "available_in_il": True,
                "data_quality": "partial",   # no nutrition from this source
                "price_ils": row.get("price_ils"),
                "price_per_100g_ils": row.get("price_per_100g_ils"),
            }
            _insert_product(con, rec)
    LOG.info("transparency: %d SKUs touched", len(rows))
    return len(rows)


def _coerce_float(v) -> float | None:
    if v in (None, "", "NA"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---- Linking & taxonomy assignment -------------------------------------

def _link_by_name(con: duckdb.DuckDBPyConnection) -> int:
    """Best-effort: cross-link OFF products with transparency rows by name."""
    rows = con.execute(
        "SELECT canonical_id, name_he, brand FROM products WHERE source = 'off'"
    ).fetchall()
    transp = con.execute(
        "SELECT canonical_id, name_he FROM products WHERE source = 'transparency'"
    ).fetchall()
    transp_map = {t[1]: t[0] for t in transp}

    linked = 0
    for off_id, off_name, off_brand in rows:
        q = f"{off_name} {off_brand or ''}".strip()
        best = max(
            (fuzz.WRatio(q, t_name) for t_name in transp_map),
            default=0,
        )
        if best >= 88:
            con.execute(
                "UPDATE products SET available_in_il = TRUE WHERE canonical_id = ?",
                [off_id],
            )
            linked += 1
    return linked


# ---- Entry point --------------------------------------------------------

def run(off_limit: int | None = None, skip: Iterable[str] = ()) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    with connect() as con:
        reset(con)
        init_schema(con)
        _seed_taxonomy(con)
        if "tzameret" not in skip:
            _load_tzameret(con)
        if "off" not in skip:
            _load_off(con, limit=off_limit)
        if "transparency" not in skip:
            _load_transparency(con)
            _link_by_name(con)
        n = con.execute("SELECT count(*) FROM products").fetchone()[0]
        LOG.info("DONE. %d products in nutricart.duckdb", n)


def _cli() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--off-limit", type=int, default=None,
                   help="Cap OFF records (useful for dev runs).")
    p.add_argument("--skip", nargs="*", default=[],
                   choices=["tzameret", "off", "transparency"])
    args = p.parse_args()
    run(off_limit=args.off_limit, skip=args.skip)


if __name__ == "__main__":  # pragma: no cover
    _cli()
    sys.exit(0)
