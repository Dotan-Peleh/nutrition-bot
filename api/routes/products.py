"""Product lookup + fuzzy search routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from rapidfuzz import fuzz, process

from core.hebrew import normalize
from schemas.products import Nutrients, Product

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/{canonical_id}", response_model=Product)
def get_product(canonical_id: str, request: Request) -> Product:
    con = request.app.state.db
    row = con.execute(
        "SELECT canonical_id, name_he, name_en, brand, category_id, barcode, "
        "       source, serving_size_g, available_in_il, data_quality "
        "FROM products WHERE canonical_id = ?",
        [canonical_id],
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="product not found")
    nut_rows = con.execute(
        "SELECT nutrient_code, value FROM nutrients WHERE product_id = ?",
        [canonical_id],
    ).fetchall()
    nutrients = Nutrients(**{code: float(val) for code, val in nut_rows})
    return Product(
        canonical_id=row[0], name_he=row[1], name_en=row[2], brand=row[3],
        category_id=row[4], barcode=row[5], source=row[6], serving_size_g=row[7],
        available_in_il=bool(row[8]), data_quality=row[9], nutrients=nutrients,
    )


@router.post("/search")
def search(q: str = Query(..., min_length=1), limit: int = 10, *, request: Request) -> list[dict]:
    con = request.app.state.db
    q_norm = normalize(q)
    rows = con.execute(
        "SELECT canonical_id, name_he, brand FROM products WHERE name_he IS NOT NULL"
    ).fetchall()
    if not rows:
        return []
    pool = {r[0]: normalize(f"{r[1]} {r[2] or ''}") for r in rows}
    hits = process.extract(q_norm, pool, scorer=fuzz.WRatio, limit=limit)
    by_id = {r[0]: r for r in rows}
    return [
        {"canonical_id": cid, "name_he": by_id[cid][1], "brand": by_id[cid][2], "score": s}
        for (_, s, cid) in hits
    ]
