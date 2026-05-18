"""Outbound response schemas."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from schemas.products import Nutrients

NutriGrade = Literal["A", "B", "C", "D", "E"]


class RedLabelFlag(BaseModel):
    nutrient: Literal["sodium", "sugar", "sat_fat"]
    threshold: float
    actual: float
    unit: str
    penalty: int


class ProfilePenalty(BaseModel):
    reason: str
    penalty: int


class ScoreBreakdown(BaseModel):
    nutri_score_grade: NutriGrade
    nutri_score_base: int
    red_label_flags: list[RedLabelFlag] = Field(default_factory=list)
    profile_penalties: list[ProfilePenalty] = Field(default_factory=list)
    incompatible_with_profile: bool = False
    final_score: int


class AlternativeDelta(BaseModel):
    canonical_id: str
    name_he: str
    brand: str | None = None
    score: int
    score_delta: int
    explanation: str
    nutrients: Nutrients | None = None
    image_url: str | None = None


class AnalyzedItem(BaseModel):
    raw: str
    matched_canonical_id: str | None = None
    matched_name_he: str | None = None
    matched_brand: str | None = None
    matched_via: str | None = None
    match_confidence: float = 0.0
    qty: float = 1.0
    category_id: str | None = None
    image_url: str | None = None
    nutrients: Nutrients | None = None
    score: ScoreBreakdown | None = None
    alternatives: list[AlternativeDelta] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CartSummary(BaseModel):
    total_score: int
    grade_distribution: dict[NutriGrade, int]
    worst_offenders: list[str]
    avg_sodium_mg_per_100g: float
    avg_sat_fat_g_per_100g: float
    avg_sugars_g_per_100g: float


class AnalyzeResponse(BaseModel):
    items: list[AnalyzedItem]
    cart: CartSummary
    meta: dict = Field(default_factory=lambda: {
        "disclaimer": "Not medical advice. For dietary guidance consult a professional.",
        "version": "0.1.0",
    })
