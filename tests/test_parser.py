"""Offline-path parser tests. LLM path is exercised manually."""
from core.parser import parse_offline


def test_parses_newline_separated():
    items = parse_offline("קוטג' תנובה 5%\nבמבה אסם\nחלב 3% טרה")
    assert len(items) == 3
    raws = [i.raw for i in items]
    assert "במבה אסם" in raws


def test_extracts_quantity_prefix():
    items = parse_offline(["2 יוגורט", "0.5 חלב"])
    assert items[0].qty == 2.0
    assert items[1].qty == 0.5


def test_extracts_brand_when_inline():
    items = parse_offline(["קוטג' תנובה 5%"])
    assert items[0].brand == "תנובה"


def test_handles_unicode_fractions():
    items = parse_offline(["½ ק\"ג חלב"])
    # The fraction is normalized to '0.5', the regex prefix should pick it up.
    assert items[0].qty == 0.5
