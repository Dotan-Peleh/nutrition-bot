"""DuckDB schema + connection helper.

The database is a single file (default `./data/nutricart.duckdb`) populated by
`data.etl`. Schema is intentionally permissive — sources disagree on what
counts as a SKU, so cleanup happens during ETL merge, not at write time.
"""
from __future__ import annotations

import os
from pathlib import Path

import duckdb

DEFAULT_DB_PATH = Path(__file__).parent / "nutricart.duckdb"


def db_path() -> Path:
    return Path(os.environ.get("NUTRICART_DB_PATH", DEFAULT_DB_PATH))


def connect(path: Path | str | None = None, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    p = Path(path) if path else db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(p), read_only=read_only)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS categories (
    category_id   TEXT PRIMARY KEY,
    parent_id     TEXT,
    name_he       TEXT NOT NULL,
    name_en       TEXT,
    kind          TEXT NOT NULL CHECK (kind IN ('solid', 'beverage'))
);

CREATE TABLE IF NOT EXISTS products (
    canonical_id     TEXT PRIMARY KEY,
    name_he          TEXT NOT NULL,
    name_en          TEXT,
    brand            TEXT,
    category_id      TEXT REFERENCES categories(category_id),
    barcode          TEXT,
    source           TEXT NOT NULL,             -- 'tzameret' | 'off' | 'transparency'
    source_id        TEXT NOT NULL,
    serving_size_g   DOUBLE,
    available_in_il  BOOLEAN DEFAULT FALSE,
    data_quality     TEXT DEFAULT 'ok'          -- 'ok' | 'partial' | 'low'
);

CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_brand    ON products(brand);
CREATE INDEX IF NOT EXISTS idx_products_barcode  ON products(barcode);

CREATE TABLE IF NOT EXISTS nutrients (
    product_id      TEXT NOT NULL REFERENCES products(canonical_id),
    nutrient_code   TEXT NOT NULL,              -- energy_kj, sat_fat_g, sugars_g,
                                                -- sodium_mg, fiber_g, protein_g, fvl_pct
    value           DOUBLE NOT NULL,
    unit            TEXT,
    PRIMARY KEY (product_id, nutrient_code)
);

CREATE INDEX IF NOT EXISTS idx_nutrients_code ON nutrients(nutrient_code);

CREATE TABLE IF NOT EXISTS aliases (
    product_id   TEXT NOT NULL REFERENCES products(canonical_id),
    alias_he     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_aliases_text ON aliases(alias_he);

-- Phase 3b only; created empty for forward compatibility.
CREATE TABLE IF NOT EXISTS embeddings (
    product_id   TEXT PRIMARY KEY REFERENCES products(canonical_id),
    vec          FLOAT[384]
);
"""


def init_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(SCHEMA_SQL)


def reset(con: duckdb.DuckDBPyConnection) -> None:
    """Drop every table and re-create. Used at the top of ETL."""
    for table in ("embeddings", "aliases", "nutrients", "products", "categories"):
        con.execute(f"DROP TABLE IF EXISTS {table}")
    init_schema(con)
