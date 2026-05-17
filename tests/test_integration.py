"""End-to-end smoke test against the FastAPI app, with synthetic data."""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from api.main import create_app


@pytest.fixture
def client(seeded_db):
    app = create_app()
    # Override the lifespan-managed connection with the seeded one
    app.state.db = seeded_db
    # Re-seed the taxonomy table since seeded_db came from the `db` fixture
    # which already seeded categories.
    with TestClient(app) as c:
        c.app.state.db = seeded_db   # override after lifespan ran
        yield c


def test_analyze_endpoint_returns_valid_schema(client):
    payload = {"items": ["קוטג 5% תנובה", "במבה אסם"], "profile": {"low_sodium": True}}
    r = client.post("/analyze", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["items"]) == 2
    assert "cart" in body
    assert body["meta"]["disclaimer"]


def test_analyze_completes_within_budget(client):
    payload = {"items": ["קוטג 5% תנובה", "במבה אסם", "חלב 3% טרה",
                          "לחם אחיד", "קוטג 9%"]}
    t0 = time.perf_counter()
    r = client.post("/analyze", json=payload)
    elapsed = time.perf_counter() - t0
    assert r.status_code == 200
    assert elapsed < 3.0, f"too slow: {elapsed:.2f}s"


def test_score_endpoint_pure(client):
    r = client.post("/score", json={
        "energy_kj": 460, "sat_fat_g": 3, "sugars_g": 3,
        "sodium_mg": 380, "protein_g": 11,
        "kind": "solid", "profile": {"low_sodium": True},
    })
    assert r.status_code == 200
    body = r.json()
    assert body["nutri_score_grade"] in ("A", "B", "C", "D", "E")
    # low_sodium profile w/ 380mg → at least one penalty entry
    assert any("sodium" in p["reason"] for p in body["profile_penalties"])


def test_version_and_healthz(client):
    assert client.get("/version").json()["version"]
    assert client.get("/healthz").json()["ok"] is True


def test_cottage_5_finds_alternative(client):
    r = client.post("/analyze", json={"items": ["קוטג 5% תנובה"]})
    body = r.json()
    item = body["items"][0]
    assert item["matched_canonical_id"] == "tnuva_cottage_5"
    alt_ids = [a["canonical_id"] for a in item["alternatives"]]
    assert "tnuva_cottage_3" in alt_ids
