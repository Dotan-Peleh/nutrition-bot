from core.red_label import flags, total_penalty
from schemas.products import Nutrients


def test_no_flags_when_under_thresholds():
    n = Nutrients(sodium_mg=100, sugars_g=2, sat_fat_g=1)
    assert flags(n, "solid") == []
    assert total_penalty([]) == 0


def test_all_three_flags_solid():
    n = Nutrients(sodium_mg=500, sugars_g=10, sat_fat_g=8)
    fl = flags(n, "solid")
    nutrients_flagged = {f.nutrient for f in fl}
    assert nutrients_flagged == {"sodium", "sugar", "sat_fat"}
    assert total_penalty(fl) == 45


def test_beverage_uses_beverage_thresholds():
    # 350mg sodium in a beverage → flagged (threshold 300)
    n = Nutrients(sodium_mg=350)
    assert any(f.nutrient == "sodium" for f in flags(n, "beverage"))
    # 350mg in a solid → not flagged (threshold 400)
    assert not any(f.nutrient == "sodium" for f in flags(n, "solid"))


def test_boundary_inclusive_threshold():
    # Exactly at threshold → flag fires (≥, not >)
    n = Nutrients(sodium_mg=400)
    assert any(f.nutrient == "sodium" for f in flags(n, "solid"))
