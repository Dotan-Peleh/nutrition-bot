"""Nutri-Score core algorithm — sanity tests + grade-band coverage.

Full OFF parity is gated behind `test_nutriscore_parity.py` with a hand-curated
fixture; this file ensures the algorithm produces the expected band for
representative inputs.
"""
from core.nutriscore import compute, water_override
from schemas.products import Nutrients


def test_water_is_grade_a_when_overridden():
    res = water_override()
    assert res.grade == "A"
    assert res.score_0_100 == 90


def test_plain_water_solid_path():
    # Pure water nutrients: zero of everything.
    n = Nutrients()
    res = compute(n, kind="beverage")
    # All zeroes → 0 neg, 0 pos → 0 points → grade B for beverages (water_override needed for A).
    assert res.grade in ("A", "B")


def test_clearly_unhealthy_snack_is_d_or_e():
    # Crisps-ish: high energy, high sat-fat, high sodium, no fiber/protein/fvl
    n = Nutrients(energy_kj=2300, sat_fat_g=5, sugars_g=2, sodium_mg=900,
                  fiber_g=1, protein_g=6, fvl_pct=0)
    res = compute(n, kind="solid")
    assert res.grade in ("D", "E")


def test_healthy_legumes_is_a_or_b():
    # Cooked lentils: low energy, no sat-fat, low sodium, high fiber, high protein
    n = Nutrients(energy_kj=480, sat_fat_g=0.1, sugars_g=1.5, sodium_mg=10,
                  fiber_g=8, protein_g=9, fvl_pct=100)
    res = compute(n, kind="solid")
    assert res.grade in ("A", "B")


def test_sugary_soda_is_d_or_e():
    n = Nutrients(energy_kj=180, sat_fat_g=0, sugars_g=11, sodium_mg=10,
                  fiber_g=0, protein_g=0, fvl_pct=0)
    res = compute(n, kind="beverage")
    assert res.grade in ("D", "E")


def test_score_to_grade_mapping_is_monotonic():
    grades = []
    sugars_levels = [0, 5, 10, 20, 40]
    for sg in sugars_levels:
        n = Nutrients(energy_kj=2000, sat_fat_g=5, sugars_g=sg, sodium_mg=500)
        grades.append(compute(n, "solid").score_0_100)
    # As sugar increases the score must not increase
    assert all(grades[i] >= grades[i+1] for i in range(len(grades)-1))
