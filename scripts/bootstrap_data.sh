#!/usr/bin/env bash
# One-shot ETL — builds nutricart.duckdb from all three sources.
# Use --off-limit during dev to cap OFF records.
set -euo pipefail

cd "$(dirname "$0")/.."
python -m data.etl "$@"
