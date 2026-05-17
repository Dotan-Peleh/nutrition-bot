"""Profile-driven score adjustments.

Each profile flag turns on extra penalties (or hard vetoes) tuned for that
dietary need. Penalty values are MVP defaults — easy to tune as data accrues.
"""
from __future__ import annotations

from schemas.products import Nutrients
from schemas.requests import Profile
from schemas.responses import ProfilePenalty

# Categories that imply lactose presence by default
LACTOSE_CATEGORIES = {
    "milk", "cottage", "yogurt", "hard_cheese", "soft_cheese",
    "cream", "butter", "dairy_dessert",
}

# Categories that imply gluten presence by default
GLUTEN_CATEGORIES = {
    "bread_white", "bread_whole", "pita", "pastry",
    "cereal_sugary", "cereal_plain", "granola", "cookies",
    "rice_pasta",  # pasta dominant — refined further at SKU level later
}


def penalties(
    nutrients: Nutrients,
    profile: Profile,
    category_id: str | None = None,
) -> tuple[list[ProfilePenalty], bool]:
    """Return (penalties, incompatible_flag).

    `incompatible_flag=True` means the product is hard-incompatible with the
    profile (e.g. dairy for a lactose-free user) and the caller should force
    the final score to 0.
    """
    out: list[ProfilePenalty] = []
    incompatible = False

    if profile.diabetic:
        if nutrients.sugars_g > 20:
            out.append(ProfilePenalty(reason="diabetic: sugar > 20g/100g", penalty=20))
        elif nutrients.sugars_g > 10:
            out.append(ProfilePenalty(reason="diabetic: sugar > 10g/100g", penalty=10))

    if profile.low_sodium:
        if nutrients.sodium_mg > 400:
            out.append(ProfilePenalty(reason="low-sodium: sodium > 400mg/100g", penalty=20))
        elif nutrients.sodium_mg > 200:
            out.append(ProfilePenalty(reason="low-sodium: sodium > 200mg/100g", penalty=10))

    if profile.high_protein and nutrients.protein_g < 5:
        out.append(ProfilePenalty(reason="high-protein target: protein < 5g/100g", penalty=5))

    if profile.lactose_free and category_id in LACTOSE_CATEGORIES:
        out.append(ProfilePenalty(reason="lactose-free: dairy category", penalty=100))
        incompatible = True

    if profile.gluten_free and category_id in GLUTEN_CATEGORIES:
        out.append(ProfilePenalty(reason="gluten-free: gluten category", penalty=100))
        incompatible = True

    return out, incompatible


def total_penalty(plist: list[ProfilePenalty]) -> int:
    return sum(p.penalty for p in plist)
