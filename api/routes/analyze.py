"""POST /analyze — the main endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Request

from core import alternatives as alt_mod
from core import matcher as matcher_mod
from core import parser as parser_mod
from core import scorer as scorer_mod
from core.cart import summarize
from data.taxonomy import all_ids
from schemas.products import Nutrients
from schemas.requests import AnalyzeRequest
from schemas.responses import AnalyzedItem, AnalyzeResponse

router = APIRouter(tags=["analyze"])


def _load_nutrients_one(con, product_id: str) -> Nutrients:
    rows = con.execute(
        "SELECT nutrient_code, value FROM nutrients WHERE product_id = ?",
        [product_id],
    ).fetchall()
    return Nutrients(**{code: float(val) for code, val in rows})


def _load_product_meta(con, product_id: str) -> tuple[str, str | None, str | None]:
    row = con.execute(
        "SELECT name_he, brand, category_id FROM products WHERE canonical_id = ?",
        [product_id],
    ).fetchone()
    if not row:
        return ("", None, None)
    return row[0], row[1], row[2]


def _load_image_url(con, product_id: str) -> str | None:
    row = con.execute(
        "SELECT image_url FROM products WHERE canonical_id = ?", [product_id]
    ).fetchone()
    return row[0] if row else None


def _load_price(con, product_id: str) -> tuple[float | None, float | None]:
    row = con.execute(
        "SELECT price_ils, price_per_100g_ils FROM products WHERE canonical_id = ?",
        [product_id],
    ).fetchone()
    return (row[0], row[1]) if row else (None, None)


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest, request: Request) -> AnalyzeResponse:
    con = request.app.state.db
    parsed = parser_mod.parse(req.items, category_ids=all_ids())

    analyzed: list[AnalyzedItem] = []
    nutrients_by_id: dict[str, Nutrients] = {}

    for p in parsed:
        item = AnalyzedItem(raw=p.raw, qty=p.qty)
        m = matcher_mod.match(p, con)
        if not m.product_id:
            item.notes.append("no match")
            analyzed.append(item)
            continue

        item.matched_canonical_id = m.product_id
        item.matched_name_he = m.name_he
        item.matched_brand = m.brand
        item.matched_via = m.matched_via
        item.match_confidence = m.confidence
        item.category_id = m.category_id

        nutrients = _load_nutrients_one(con, m.product_id)
        item.image_url = _load_image_url(con, m.product_id)
        item.price_ils, item.price_per_100g_ils = _load_price(con, m.product_id)
        # Don't fake a Nutri-Score when the data is too thin. Require sodium
        # (dominant IL signal) plus at least one of sat fat / sugars.
        if not (nutrients.sodium_mg > 0 and (
            nutrients.sat_fat_g > 0 or nutrients.sugars_g > 0
        )):
            item.notes.append("no_nutrition_data")
            analyzed.append(item)
            continue
        nutrients_by_id[m.product_id] = nutrients
        item.nutrients = nutrients
        breakdown = scorer_mod.score(nutrients, m.category_id, req.profile)
        item.score = breakdown

        item.alternatives = alt_mod.find(
            con,
            current_id=m.product_id,
            current_score=breakdown.final_score,
            category_id=m.category_id,
            profile=req.profile,
        )
        analyzed.append(item)

    cart = summarize(analyzed, nutrients_by_id)
    return AnalyzeResponse(items=analyzed, cart=cart)
