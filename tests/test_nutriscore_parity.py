"""Parity check against a hand-curated fixture.

Goal: ≥ 80% of the products land in the expected grade band.
The 2023 algorithm changed quite a bit from OFF's older grades, so we
allow ±1 band tolerance (e.g. fixture says 'C' → we accept B/C/D).
"""
import json

from core.nutriscore import compute
from schemas.products import Nutrients

GRADE_ORDER = ["A", "B", "C", "D", "E"]


def _within_one(actual: str, expected: str) -> bool:
    return abs(GRADE_ORDER.index(actual) - GRADE_ORDER.index(expected)) <= 1


def test_score_parity_fixture(fixtures_dir):
    cases = json.loads((fixtures_dir / "off_score_parity.json").read_text())
    hits = 0
    misses = []
    for case in cases:
        n = Nutrients(**case["nutrients"])
        actual = compute(n, case["kind"]).grade
        if _within_one(actual, case["expected_grade"]):
            hits += 1
        else:
            misses.append((case["name"], case["expected_grade"], actual))
    rate = hits / len(cases)
    assert rate >= 0.80, f"parity {rate:.0%} — misses: {misses}"
