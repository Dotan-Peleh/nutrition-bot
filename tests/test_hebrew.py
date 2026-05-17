from core.hebrew import normalize, normalize_numerics


def test_normalize_strips_niqqud_and_finals():
    # קוֹטֶג' תנובה — with niqqud and geresh
    assert normalize("קוֹטֶג' תנובה") == "קוטג תנובה"


def test_normalize_folds_finals():
    # final mem at the end of "לחם" should fold to base mem
    assert normalize("לחם לבן") == "לחמ לבנ"


def test_normalize_collapses_whitespace():
    assert normalize("  חלב   3%   טרה  ") == "חלב 3% טרה"


def test_normalize_empty():
    assert normalize("") == ""
    assert normalize("   ") == ""


def test_normalize_numerics_unicode_fractions():
    assert normalize_numerics("½ ק\"ג") == "0.5 ק\"ג"
    assert normalize_numerics("¾ של חלב") == "0.75 של חלב"
