"""Alternatives finder — same category, higher score, IL-available."""
from core import scorer as scorer_mod
from core.alternatives import find
from schemas.products import Nutrients
from schemas.requests import Profile


def _score_for(db, product_id: str, profile: Profile | None = None) -> int:
    profile = profile or Profile()
    rows = db.execute(
        "SELECT nutrient_code, value FROM nutrients WHERE product_id = ?",
        [product_id],
    ).fetchall()
    n = Nutrients(**{code: float(v) for code, v in rows})
    cat = db.execute(
        "SELECT category_id FROM products WHERE canonical_id = ?", [product_id]
    ).fetchone()[0]
    return scorer_mod.score(n, cat, profile).final_score


def test_cottage_5_gets_cottage_3_as_alternative(seeded_db):
    current = _score_for(seeded_db, "tnuva_cottage_5")
    alts = find(seeded_db, "tnuva_cottage_5", current, "cottage", Profile())
    alt_ids = [a.canonical_id for a in alts]
    assert "tnuva_cottage_3" in alt_ids
    # 9% should NOT appear — same/worse score
    assert "strauss_cottage_9" not in alt_ids


def test_alternatives_respect_lactose_free_profile(seeded_db):
    current = _score_for(seeded_db, "tnuva_cottage_5", Profile(lactose_free=True))
    alts = find(seeded_db, "tnuva_cottage_5", current, "cottage",
                Profile(lactose_free=True))
    # All dairy alternatives are incompatible — list must be empty
    assert alts == []


def test_no_alternatives_when_already_best(seeded_db):
    current = _score_for(seeded_db, "tnuva_cottage_3")
    alts = find(seeded_db, "tnuva_cottage_3", current, "cottage", Profile())
    assert alts == []


def test_alternative_explanation_mentions_sodium_drop(seeded_db):
    current = _score_for(seeded_db, "tnuva_cottage_5")
    alts = find(seeded_db, "tnuva_cottage_5", current, "cottage", Profile())
    cottage_3 = next(a for a in alts if a.canonical_id == "tnuva_cottage_3")
    assert "נתרן" in cottage_3.explanation
