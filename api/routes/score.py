"""POST /score — score raw nutrients directly, no matcher involved."""
from __future__ import annotations

from fastapi import APIRouter

from core import scorer as scorer_mod
from schemas.products import Nutrients
from schemas.requests import ScoreRequest
from schemas.responses import ScoreBreakdown

router = APIRouter(tags=["score"])


@router.post("/score", response_model=ScoreBreakdown)
def score(req: ScoreRequest) -> ScoreBreakdown:
    nutrients = Nutrients(
        energy_kj=req.energy_kj,
        sat_fat_g=req.sat_fat_g,
        sugars_g=req.sugars_g,
        sodium_mg=req.sodium_mg,
        fiber_g=req.fiber_g,
        protein_g=req.protein_g,
        fvl_pct=req.fvl_pct,
    )
    # Force kind by faking a category mapping
    category_id = "milk" if req.kind == "beverage" else "cottage"
    return scorer_mod.score(nutrients, category_id=category_id, profile=req.profile)
