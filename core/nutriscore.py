"""Nutri-Score (2023 algorithm).

Two variants — `solid` (general foods) and `beverage`. Cheese & added-fats
sub-rules are intentionally NOT implemented in MVP; revisit when ETL surfaces
enough of those categories to matter.

Points tables come from the 2023 official update (Santé Publique France).
Sources cross-referenced against Open Food Facts' open implementation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from schemas.products import Nutrients

Kind = Literal["solid", "beverage"]
Grade = Literal["A", "B", "C", "D", "E"]


# ---------- Negative-points tables (higher = less healthy) ----------

# Energy (kJ / 100g) — solids
_ENERGY_SOLID = [335, 670, 1005, 1340, 1675, 2010, 2345, 2680, 3015, 3350]
# Energy (kJ / 100ml) — beverages (2023 update — stricter)
_ENERGY_BEV   = [30, 90, 150, 210, 240, 270, 300, 330, 360, 390]

# Sugars (g / 100g) — solids (2023 update; tighter than 2017)
_SUGAR_SOLID = [3.4, 6.8, 10, 14, 17, 20, 24, 27, 31, 34, 37, 41, 44, 48, 51]
# Sugars (g / 100ml) — beverages (2023; tighter)
_SUGAR_BEV   = [0.5, 2, 3.5, 5, 6, 7, 8, 9, 10, 11]

# Saturated fat (g / 100g)
_SATFAT_SOLID = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
_SATFAT_BEV   = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

# Sodium (mg / 100g)
_SODIUM_SOLID = [80, 160, 240, 320, 400, 480, 560, 640, 720, 800,
                 880, 960, 1040, 1120, 1200, 1280, 1360, 1440, 1520, 1600]
_SODIUM_BEV   = _SODIUM_SOLID  # same scale per 2023 update


# ---------- Positive-points tables (higher = more healthy) ----------

# Fiber (g / 100g)
_FIBER = [3.0, 4.1, 5.2, 6.3, 7.4]
# Protein (g / 100g) — solids
_PROTEIN_SOLID = [2.4, 4.8, 7.2, 9.6, 12, 14, 17]
# Protein (g / 100ml) — beverages
_PROTEIN_BEV   = [1.2, 1.5, 1.8, 2.1, 2.4, 2.7, 3.0]
# Fruits/veg/legumes (%)
_FVL_SOLID = [40, 60, 80]      # 1/2/5 points
_FVL_BEV   = [40, 60, 80]


def _points_above(value: float, thresholds: list[float]) -> int:
    """Number of thresholds the value crosses (0-indexed → integer points)."""
    n = 0
    for t in thresholds:
        if value > t:
            n += 1
        else:
            break
    return n


def _fvl_points(value: float, table: list[float], kind: Kind) -> int:
    # 0–5 (solids) / 0–10 (beverages); we use the simplified table common in OFF.
    if value > 80:
        return 10 if kind == "beverage" else 5
    if value > 60:
        return 2
    if value > 40:
        return 1
    return 0


@dataclass(frozen=True)
class NutriScoreResult:
    grade: Grade
    raw_points: int
    score_0_100: int
    negative_points: int
    positive_points: int


def _grade_from_points(points: int, kind: Kind) -> Grade:
    if kind == "solid":
        if points <= 0:
            return "A"
        if points <= 2:
            return "B"
        if points <= 10:
            return "C"
        if points <= 18:
            return "D"
        return "E"
    # beverage — water can be A; otherwise stricter
    if points <= 1:
        return "B"
    if points <= 5:
        return "C"
    if points <= 9:
        return "D"
    return "E"


_GRADE_TO_SCORE: dict[Grade, int] = {"A": 90, "B": 70, "C": 50, "D": 30, "E": 10}


def compute(nutrients: Nutrients, kind: Kind = "solid") -> NutriScoreResult:
    if kind == "beverage":
        neg = (
            _points_above(nutrients.energy_kj, _ENERGY_BEV)
            + _points_above(nutrients.sugars_g, _SUGAR_BEV)
            + _points_above(nutrients.sat_fat_g, _SATFAT_BEV)
            + _points_above(nutrients.sodium_mg, _SODIUM_BEV)
        )
        pos = (
            _points_above(nutrients.fiber_g, _FIBER)
            + _points_above(nutrients.protein_g, _PROTEIN_BEV)
            + _fvl_points(nutrients.fvl_pct, _FVL_BEV, "beverage")
        )
    else:
        neg = (
            _points_above(nutrients.energy_kj, _ENERGY_SOLID)
            + _points_above(nutrients.sugars_g, _SUGAR_SOLID)
            + _points_above(nutrients.sat_fat_g, _SATFAT_SOLID)
            + _points_above(nutrients.sodium_mg, _SODIUM_SOLID)
        )
        pos = (
            _points_above(nutrients.fiber_g, _FIBER)
            + _points_above(nutrients.protein_g, _PROTEIN_SOLID)
            + _fvl_points(nutrients.fvl_pct, _FVL_SOLID, "solid")
        )

    # Standard rule: if negative >= 11 and fvl < 5 points (here approximated by
    # fvl_pct < 80), protein points don't count.
    if kind == "solid" and neg >= 11 and nutrients.fvl_pct <= 80:
        pos = pos - _points_above(nutrients.protein_g, _PROTEIN_SOLID)
        pos = max(0, pos)

    raw = neg - pos
    grade = _grade_from_points(raw, kind)
    return NutriScoreResult(
        grade=grade,
        raw_points=raw,
        score_0_100=_GRADE_TO_SCORE[grade],
        negative_points=neg,
        positive_points=pos,
    )


# Special case: pure water is A regardless.
def water_override() -> NutriScoreResult:
    return NutriScoreResult(grade="A", raw_points=-10, score_0_100=90,
                            negative_points=0, positive_points=10)
