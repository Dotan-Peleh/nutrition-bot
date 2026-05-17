# NutriCart

A REST service that takes a free-text Hebrew shopping list, matches each line
to a real Israeli SKU, scores it for healthfulness, and suggests a healthier
in-category alternative the user can actually buy.

> **Disclaimer:** outputs are informational only. Not medical or dietary advice.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev,etl]'

# Build the local catalog (downloads ~1 GB OFF dump first run).
python -m data.etl --off-limit 2000   # quick dev build

# Run the API
uvicorn api.main:app --reload

# Try it
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
        "items": ["קוטג'\'' תנובה 5%", "במבה אסם", "חלב 3% טרה"],
        "profile": {"low_sodium": true}
      }'
```

OpenAPI docs at `http://localhost:8000/docs`.

## Layout

```
api/      — FastAPI app + routes
core/     — parser, matcher, scorer, alternatives, cart
data/     — ETL, sources (tzameret/off/transparency), DuckDB schema, taxonomy
schemas/  — Pydantic request/response/internal models
tests/    — pytest suites + fixtures
scripts/  — bootstrap helpers
```

## How scoring works

- **Nutri-Score (2023)** baseline → A=90 / B=70 / C=50 / D=30 / E=10.
- **Israeli red-label thresholds** (MoH): each crossed threshold subtracts
  15 points and is reported in the response.
- **Profile multipliers**: `diabetic`, `low_sodium`, `high_protein`,
  `lactose_free`, `gluten_free` add weighted penalties — the last two can
  force `incompatible_with_profile=true` and zero the score.

See `core/scorer.py` for the composition and `core/nutriscore.py` for the
algorithm tables.

## Data sources

| Source | Role |
|---|---|
| Tzameret (data.gov.il CKAN) | nutrient profiles, anchor |
| Open Food Facts (IL filter) | branded long tail + Nutri-Score parity |
| Supermarket transparency XMLs | barcodes + `available_in_il` |

ETL is in `data/etl.py`; resources are re-fetched on every run.

## Tests

```bash
pytest -q
ruff check
```

The pure-logic suites (`test_nutriscore.py`, `test_red_label.py`,
`test_profile.py`, `test_scorer.py`, `test_cart.py`, `test_hebrew.py`) run
without any external data. Integration tests (`test_integration.py`,
`test_matcher.py`, `test_alternatives.py`) spin up an in-memory DuckDB with
hand-crafted fixtures.
