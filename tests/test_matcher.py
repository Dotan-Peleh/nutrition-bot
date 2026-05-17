"""Matcher accuracy on synthetic catalog."""
from core.matcher import ParsedItem, match


def test_exact_match_hits(seeded_db):
    res = match(ParsedItem(raw="קוטג 5%", brand="תנובה"), seeded_db)
    assert res.product_id == "tnuva_cottage_5"
    assert res.matched_via in ("exact", "fuzzy")
    assert res.confidence >= 0.9


def test_fuzzy_match_handles_typo_and_apostrophe(seeded_db):
    res = match(ParsedItem(raw="קוטג' תנובה 5%"), seeded_db)
    assert res.product_id == "tnuva_cottage_5"


def test_brand_only_match(seeded_db):
    res = match(ParsedItem(raw="במבה", brand="אסם"), seeded_db)
    assert res.product_id == "osem_bamba"


def test_unknown_item_returns_none(seeded_db):
    res = match(ParsedItem(raw="קוויאר רוסי משובח"), seeded_db)
    assert res.product_id is None
    assert res.matched_via == "none"


def test_alias_lookup_via_fuzzy(seeded_db):
    # 'במבה אסם' is in `aliases` for the bamba product
    res = match(ParsedItem(raw="במבה אסם"), seeded_db)
    assert res.product_id == "osem_bamba"


def test_milk_match(seeded_db):
    res = match(ParsedItem(raw="חלב 3% טרה"), seeded_db)
    assert res.product_id == "tara_milk_3"
