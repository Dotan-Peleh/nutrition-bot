"""Pydantic schemas describing internal products + nutrients."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

NutrientCode = Literal[
    "energy_kj", "sat_fat_g", "sugars_g", "sodium_mg",
    "fiber_g", "protein_g", "fvl_pct",
]


class Nutrients(BaseModel):
    """Per-100g (solids) or per-100ml (beverages) nutrient profile."""
    energy_kj: float = 0.0
    sat_fat_g: float = 0.0
    sugars_g: float = 0.0
    sodium_mg: float = 0.0
    fiber_g: float = 0.0
    protein_g: float = 0.0
    fvl_pct: float = Field(0.0, ge=0, le=100, description="Fruits/veg/legumes percent")

    def get(self, code: NutrientCode) -> float:
        return getattr(self, code)


class Product(BaseModel):
    canonical_id: str
    name_he: str
    name_en: str | None = None
    brand: str | None = None
    category_id: str | None = None
    barcode: str | None = None
    source: str
    serving_size_g: float | None = None
    available_in_il: bool = False
    data_quality: Literal["ok", "partial", "low"] = "ok"
    image_url: str | None = None
    nutrients: Nutrients
