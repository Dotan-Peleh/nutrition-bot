from core.profile import penalties, total_penalty
from schemas.products import Nutrients
from schemas.requests import Profile


def test_no_profile_means_no_penalties():
    pen, incomp = penalties(Nutrients(sugars_g=30, sodium_mg=500), Profile())
    assert pen == []
    assert incomp is False


def test_diabetic_tiered_penalty():
    n = Nutrients(sugars_g=25)
    pen, _ = penalties(n, Profile(diabetic=True))
    assert len(pen) == 1
    assert pen[0].penalty == 20

    pen2, _ = penalties(Nutrients(sugars_g=12), Profile(diabetic=True))
    assert pen2[0].penalty == 10

    pen3, _ = penalties(Nutrients(sugars_g=4), Profile(diabetic=True))
    assert pen3 == []


def test_low_sodium_tiered_penalty():
    pen, _ = penalties(Nutrients(sodium_mg=450), Profile(low_sodium=True))
    assert total_penalty(pen) == 20
    pen2, _ = penalties(Nutrients(sodium_mg=250), Profile(low_sodium=True))
    assert total_penalty(pen2) == 10


def test_lactose_free_hard_veto_on_dairy_category():
    pen, incomp = penalties(Nutrients(), Profile(lactose_free=True),
                            category_id="cottage")
    assert incomp is True
    assert any("lactose" in p.reason for p in pen)


def test_lactose_free_does_not_block_non_dairy():
    pen, incomp = penalties(Nutrients(), Profile(lactose_free=True),
                            category_id="puffed")
    assert incomp is False
    assert pen == []


def test_gluten_free_hard_veto_on_bread():
    pen, incomp = penalties(Nutrients(), Profile(gluten_free=True),
                            category_id="bread_white")
    assert incomp is True


def test_high_protein_penalty_under_threshold():
    pen, _ = penalties(Nutrients(protein_g=3), Profile(high_protein=True))
    assert len(pen) == 1 and pen[0].penalty == 5
    pen2, _ = penalties(Nutrients(protein_g=8), Profile(high_protein=True))
    assert pen2 == []
