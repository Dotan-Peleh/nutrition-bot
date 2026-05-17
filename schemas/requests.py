"""Inbound request schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Profile(BaseModel):
    diabetic: bool = False
    low_sodium: bool = False
    high_protein: bool = False
    lactose_free: bool = False
    gluten_free: bool = False


class AnalyzeRequest(BaseModel):
    items: list[str] = Field(..., min_length=1, max_length=100)
    profile: Profile = Field(default_factory=Profile)


class ScoreRequest(BaseModel):
    """Score raw nutrients without going through parser/matcher."""
    energy_kj: float = 0.0
    sat_fat_g: float = 0.0
    sugars_g: float = 0.0
    sodium_mg: float = 0.0
    fiber_g: float = 0.0
    protein_g: float = 0.0
    fvl_pct: float = 0.0
    kind: str = "solid"
    profile: Profile = Field(default_factory=Profile)
