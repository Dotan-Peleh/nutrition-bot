from core.cart import summarize
from schemas.products import Nutrients
from schemas.responses import AnalyzedItem, ScoreBreakdown


def _item(name: str, score_v: int, grade: str, qty: float = 1.0) -> AnalyzedItem:
    return AnalyzedItem(
        raw=name,
        matched_canonical_id=name,
        matched_name_he=name,
        qty=qty,
        score=ScoreBreakdown(
            nutri_score_grade=grade,  # type: ignore[arg-type]
            nutri_score_base=score_v,
            final_score=score_v,
        ),
    )


def test_empty_cart_returns_zero():
    s = summarize([], {})
    assert s.total_score == 0
    assert s.grade_distribution == {}


def test_weighted_average_score():
    items = [_item("a", 30, "D"), _item("b", 80, "B")]
    nutrients = {"a": Nutrients(sodium_mg=500, sat_fat_g=4),
                 "b": Nutrients(sodium_mg=50,  sat_fat_g=1)}
    s = summarize(items, nutrients)
    # Equal weights → mean = 55
    assert s.total_score == 55


def test_worst_offender_first():
    items = [_item("good", 90, "A"), _item("bad", 10, "E"), _item("ok", 60, "C")]
    s = summarize(items, {})
    assert s.worst_offenders[0] == "bad"


def test_grade_distribution_count():
    items = [_item("a", 90, "A"), _item("b", 90, "A"), _item("c", 30, "D")]
    s = summarize(items, {})
    assert s.grade_distribution == {"A": 2, "D": 1}
