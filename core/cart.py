"""Cart-level aggregation."""
from __future__ import annotations

from collections import Counter

from schemas.products import Nutrients
from schemas.responses import AnalyzedItem, CartSummary, NutriGrade


def _weight(item: AnalyzedItem, default_serving_g: float = 100.0) -> float:
    # Use the qty as a multiplier on serving size; serving size unknown → 100g.
    return item.qty * default_serving_g


def summarize(items: list[AnalyzedItem], nutrients_by_id: dict[str, Nutrients]) -> CartSummary:
    if not items:
        return CartSummary(
            total_score=0,
            grade_distribution={},
            worst_offenders=[],
            avg_sodium_mg_per_100g=0.0,
            avg_sat_fat_g_per_100g=0.0,
            avg_sugars_g_per_100g=0.0,
        )

    scored = [i for i in items if i.score is not None]
    if not scored:
        return CartSummary(
            total_score=0,
            grade_distribution={},
            worst_offenders=[i.raw for i in items[:3]],
            avg_sodium_mg_per_100g=0.0,
            avg_sat_fat_g_per_100g=0.0,
            avg_sugars_g_per_100g=0.0,
        )

    total_w = sum(_weight(i) for i in scored) or 1.0
    weighted_score = sum(i.score.final_score * _weight(i) for i in scored) / total_w  # type: ignore[union-attr]

    grade_counter: Counter[NutriGrade] = Counter(
        i.score.nutri_score_grade for i in scored  # type: ignore[union-attr]
    )

    # Worst offenders: highest "score deficit" weighted by qty
    ordered = sorted(
        scored,
        key=lambda i: (100 - i.score.final_score) * _weight(i),  # type: ignore[union-attr]
        reverse=True,
    )
    worst = [i.matched_name_he or i.raw for i in ordered[:3]]

    # Cart-level nutrient averages (weighted by serving × qty)
    s_na = s_sf = s_sg = 0.0
    for i in scored:
        if not i.matched_canonical_id:
            continue
        n = nutrients_by_id.get(i.matched_canonical_id)
        if not n:
            continue
        w = _weight(i)
        s_na += n.sodium_mg * w
        s_sf += n.sat_fat_g * w
        s_sg += n.sugars_g * w

    return CartSummary(
        total_score=int(round(weighted_score)),
        grade_distribution=dict(grade_counter),
        worst_offenders=worst,
        avg_sodium_mg_per_100g=round(s_na / total_w, 2),
        avg_sat_fat_g_per_100g=round(s_sf / total_w, 2),
        avg_sugars_g_per_100g=round(s_sg / total_w, 2),
    )
