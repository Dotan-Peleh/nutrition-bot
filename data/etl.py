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
        " source, source_id, serving_size_g, available_in_il, data_quality) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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


def _load_tzameret(con: duckdb.DuckDBPyConnection) -> int:
    LOG.info("fetching Tzameret …")
    tables = tzameret.fetch_all()
    food_list = tables.get("tzameret_food_list", [])
    inserted = 0
    for row in food_list:
        rec = {
            "source": "tzameret",
            "source_id": str(row.get("smlmitzrach") or row.get("food_code") or row.get("_id") or ""),
            "name_he": row.get("shmmitzrach") or row.get("name_he") or "",
            "name_en": row.get("english_name"),
            "category_id": None,  # mapped in `_link()`
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
        _insert_product(con, rec | {"available_in_il": False})
        inserted += 1
    LOG.info("OFF: %d Israeli products", inserted)
    return inserted


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
            con.execute(
                "UPDATE products SET available_in_il = TRUE WHERE canonical_id = ?",
                [existing[0]],
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
