"""Composite scorer tests."""
from core.scorer import score
from schemas.products import Nutrients
from schemas.requests import Profile


def test_score_clamps_to_0_100():
    n = Nutrients(energy_kj=3000, sat_fat_g=20, sugars_g=50, sodium_mg=2000)
    res = score(n, category_id="puffed", profile=Profile())
    assert 0 <= res.final_score <= 100


def test_red_label_penalties_subtract_from_base():
    # Pick a high-base product (lots of fiber, no satfat/sugar) so we can
    # observe the full sodium penalty without hitting the floor clamp.
    n = Nutrients(energy_kj=400, sat_fat_g=0.5, sugars_g=2, sodium_mg=420,
                  fiber_g=8, protein_g=10)
    res = score(n, category_id="cottage", profile=Profile())
    deduction = res.nutri_score_base - res.final_score
    # exactly one red-label flag (sodium) → −15
    assert len(res.red_label_flags) == 1
    assert res.red_label_flags[0].nutrient == "sodium"
    assert deduction == 15


def test_profile_incompatible_zeros_score():
    n = Nutrients(energy_kj=300, sat_fat_g=1, sugars_g=3, sodium_mg=80, protein_g=10)
    res = score(n, category_id="cottage", profile=Profile(lactose_free=True))
    assert res.incompatible_with_profile is True
    assert res.final_score == 0


def test_beverage_kind_inferred_from_category():
    # Same nutrients, milk (beverage) should use beverage thresholds.
    n = Nutrients(energy_kj=300, sat_fat_g=2, sugars_g=5, sodium_mg=350,
                  protein_g=3.2)
    res = score(n, category_id="milk", profile=Profile())
    # 350mg sodium triggers beverage threshold of 300 but not solid threshold of 400
    sodium_flags = [f for f in res.red_label_flags if f.nutrient == "sodium"]
    assert len(sodium_flags) == 1
