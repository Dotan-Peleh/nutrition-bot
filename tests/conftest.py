"""Shared fixtures for tests."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from data.db import init_schema
from data.taxonomy import TAXONOMY


@pytest.fixture
def db() -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB with the full schema + taxonomy seeded."""
    con = duckdb.connect(":memory:")
    init_schema(con)
    con.executemany(
        "INSERT INTO categories VALUES (?, ?, ?, ?, ?)",
        [(c.category_id, c.parent_id, c.name_he, c.name_en, c.kind) for c in TAXONOMY],
    )
    yield con
    con.close()


@pytest.fixture
def seeded_db(db: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyConnection:
    """DuckDB seeded with a small synthetic catalog used by matcher /
    alternatives tests. Five products across cottage, milk, snacks, bread."""
    products = [
        # (canonical_id, name_he, brand, category_id, barcode, source, source_id,
        #  available_in_il)
        ("tnuva_cottage_5", "קוטג 5%", "תנובה", "cottage", "7290000000001", "test", "1", True),
        ("tnuva_cottage_3", "קוטג 3%", "תנובה", "cottage", "7290000000002", "test", "2", True),
        ("strauss_cottage_9", "קוטג 9%", "שטראוס", "cottage", "7290000000003", "test", "3", True),
        ("osem_bamba", "במבה", "אסם", "puffed", "7290000000010", "test", "4", True),
        ("achdut_bread", "לחם אחיד", "אחדות", "bread_white", "7290000000020", "test", "5", True),
        ("tara_milk_3", "חלב 3%", "טרה", "milk", "7290000000030", "test", "6", True),
    ]
    for pid, name, brand, cat, barcode, src, sid, avail in products:
        db.execute(
            "INSERT INTO products (canonical_id, name_he, brand, category_id, "
            "barcode, source, source_id, available_in_il, serving_size_g) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 100)",
            [pid, name, brand, cat, barcode, src, sid, avail],
        )

    # Nutrients per product (per 100g / per 100ml).
    nutrients = {
        # cottage 5% — moderate fat, low sugar, some sodium
        "tnuva_cottage_5": {"energy_kj": 460, "sat_fat_g": 3.0, "sugars_g": 3.0,
                             "sodium_mg": 380, "fiber_g": 0, "protein_g": 11, "fvl_pct": 0},
        # cottage 3% — healthier alt: less sodium, less satfat
        "tnuva_cottage_3": {"energy_kj": 340, "sat_fat_g": 1.5, "sugars_g": 3.0,
                             "sodium_mg": 250, "fiber_g": 0, "protein_g": 12, "fvl_pct": 0},
        # cottage 9% — worse: red sat-fat
        "strauss_cottage_9": {"energy_kj": 600, "sat_fat_g": 6.0, "sugars_g": 3.0,
                               "sodium_mg": 400, "fiber_g": 0, "protein_g": 10, "fvl_pct": 0},
        # bamba — very high fat, decent protein, low sodium
        "osem_bamba": {"energy_kj": 2300, "sat_fat_g": 5.0, "sugars_g": 4.5,
                        "sodium_mg": 150, "fiber_g": 4, "protein_g": 14, "fvl_pct": 0},
        # white bread — moderate everything
        "achdut_bread": {"energy_kj": 1050, "sat_fat_g": 0.5, "sugars_g": 3.0,
                         "sodium_mg": 470, "fiber_g": 3, "protein_g": 9, "fvl_pct": 0},
        # milk 3% — beverage
        "tara_milk_3": {"energy_kj": 264, "sat_fat_g": 2.0, "sugars_g": 4.8,
                         "sodium_mg": 50, "fiber_g": 0, "protein_g": 3.2, "fvl_pct": 0},
    }
    for pid, vals in nutrients.items():
        for code, val in vals.items():
            db.execute(
                "INSERT INTO nutrients VALUES (?, ?, ?, NULL)",
                [pid, code, float(val)],
            )

    # Aliases — common typos / abbreviations
    db.execute("INSERT INTO aliases VALUES ('osem_bamba', 'במבה אסם')")
    db.execute("INSERT INTO aliases VALUES ('tnuva_cottage_5', 'קוטג תנובה')")

    yield db


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"
