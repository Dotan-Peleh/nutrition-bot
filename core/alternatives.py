"""Healthier-alternative finder.

Single SQL: same category, available in IL, higher score by ≥10. Profile
constraints applied as additional filters. The score column is materialized
on demand (the API server caches a `scored_view` per profile in memory).
"""
from __future__ import annotations

from collections.abc import Iterable

import duckdb

from core import scorer as scorer_mod
from schemas.products import Nutrients
from schemas.requests import Profile
from schemas.responses import AlternativeDelta

MIN_IMPROVEMENT = 10


def _load_nutrients(con: duckdb.DuckDBPyConnection, product_ids: Iterable[str]) -> dict[str, Nutrients]:
    ids = list(product_ids)
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = con.execute(
        f"SELECT product_id, nutrient_code, value FROM nutrients "
        f"WHERE product_id IN ({placeholders})",
        ids,
    ).fetchall()
    out: dict[str, dict[str, float]] = {}
    for pid, code, value in rows:
        out.setdefault(pid, {})[code] = float(value)
    return {pid: Nutrients(**vals) for pid, vals in out.items()}


def _delta_explanation(current: Nutrients, alt: Nutrients) -> str:
    parts: list[str] = []

    def pct(a: float, b: float) -> int | None:
        if a == 0:
            return None
        return int(round((b - a) / a * 100))

    sodium = pct(current.sodium_mg, alt.sodium_mg)
    if sodium is not None and sodium <= -10:
        parts.append(f"פחות נתרן ב-{abs(sodium)}%")
    sugars = pct(current.sugars_g, alt.sugars_g)
    if sugars is not None and sugars <= -10:
        parts.append(f"פחות סוכר ב-{abs(sugars)}%")
    satfat = pct(current.sat_fat_g, alt.sat_fat_g)
    if satfat is not None and satfat <= -10:
        parts.append(f"פחות שומן רווי ב-{abs(satfat)}%")
    protein = pct(current.protein_g, alt.protein_g)
    if protein is not None and protein >= 10:
        parts.append(f"יותר חלבון ב-{protein}%")
    fiber = pct(current.fiber_g, alt.fiber_g)
    if fiber is not None and fiber >= 10:
        parts.append(f"יותר סיבים ב-{fiber}%")

    return ", ".join(parts) if parts else "פרופיל תזונתי כללי טוב יותר"


def find(
    con: duckdb.DuckDBPyConnection,
    current_id: str,
    current_score: int,
    category_id: str | None,
    profile: Profile,
    limit: int = 3,
) -> list[AlternativeDelta]:
    if not category_id:
        return []

    rows = con.execute(
        "SELECT canonical_id, name_he, brand FROM products "
        "WHERE category_id = ? AND available_in_il AND canonical_id != ?",
        [category_id, current_id],
    ).fetchall()
    if not rows:
        return []

    ids = [r[0] for r in rows] + [current_id]
    nutrients_map = _load_nutrients(con, ids)
    current_nutrients = nutrients_map.get(current_id, Nutrients())

    scored: list[tuple[int, str, str, str | None, Nutrients]] = []
    for cid, name_he, brand in rows:
        n = nutrients_map.get(cid)
        if n is None:
            continue
        breakdown = scorer_mod.score(n, category_id=category_id, profile=profile)
        if breakdown.incompatible_with_profile:
            continue
        if breakdown.final_score < current_score + MIN_IMPROVEMENT:
            continue
        scored.append((breakdown.final_score, cid, name_he, brand, n))

    scored.sort(reverse=True, key=lambda t: t[0])
    out: list[AlternativeDelta] = []
    for s, cid, name_he, brand, n in scored[:limit]:
        out.append(AlternativeDelta(
            canonical_id=cid,
            name_he=name_he,
            brand=brand,
            score=s,
            score_delta=s - current_score,
            explanation=_delta_explanation(current_nutrients, n),
        ))
    return out
