"""Composite scorer: Nutri-Score base − red-label penalties − profile penalties.

Single entry-point `score()` returns the full breakdown used in the response.
"""
from __future__ import annotations

from core import nutriscore, red_label
from core import profile as profile_mod
from data.taxonomy import is_beverage
from schemas.products import Nutrients
from schemas.requests import Profile
from schemas.responses import ScoreBreakdown


def _clamp(value: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, value))


def score(
    nutrients: Nutrients,
    category_id: str | None = None,
    profile: Profile | None = None,
) -> ScoreBreakdown:
    profile = profile or Profile()
    kind = "beverage" if is_beverage(category_id) else "solid"

    ns = nutriscore.compute(nutrients, kind)
    rl = red_label.flags(nutrients, kind)
    pp, incompatible = profile_mod.penalties(nutrients, profile, category_id)

    final = ns.score_0_100 - red_label.total_penalty(rl) - profile_mod.total_penalty(pp)
    final_clamped = 0 if incompatible else _clamp(final)

    return ScoreBreakdown(
        nutri_score_grade=ns.grade,
        nutri_score_base=ns.score_0_100,
        red_label_flags=rl,
        profile_penalties=pp,
        incompatible_with_profile=incompatible,
        final_score=final_clamped,
    )
