"""Supermarket transparency XMLs (Shufersal, Rami Levy, Victory).

Thin wrapper around the `il-supermarket-scraper` package. The scraper pulls
the latest "PriceFull" file per chain — the government-mandated full price
catalog with barcode + product name + manufacturer + price. We use it for:

  1. Mark canonical products as `available_in_il = TRUE`
  2. Supply Hebrew display names + manufacturer brand the OFF dump may lack

The library API changed in 2024 (dropped dump_folder_name + limit kwargs,
switched to FileTypesFilters enum), so this wrapper bridges that.
"""
from __future__ import annotations

import gzip
import os
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from pathlib import Path

CHAINS = ("SHUFERSAL", "RAMI_LEVY", "VICTORY")


def fetch_latest(chains: Iterable[str], dest_dir: Path) -> list[Path]:
    """Download today's PriceFull files for given chains.

    The scraper writes into the current working directory's `dumps/` subfolder
    by default. We chdir into `dest_dir`, run the scraper, then return all
    XML/gz files we find. Heavyweight — only invoke from the ETL orchestrator.
    """
    try:
        from il_supermarket_scarper import FileTypesFilters, ScarpingTask
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "il-supermarket-scraper not installed. Run: pip install '.[etl]'"
        ) from e

    dest_dir.mkdir(parents=True, exist_ok=True)
    prev_cwd = os.getcwd()
    try:
        os.chdir(dest_dir)
        task = ScarpingTask(
            enabled_scrapers=list(chains),
            files_types=[FileTypesFilters.PRICE_FULL_FILE.name],
        )
        task.start()
        task.join()
    finally:
        os.chdir(prev_cwd)
    out: list[Path] = []
    out.extend(dest_dir.rglob("*.xml"))
    out.extend(dest_dir.rglob("*.gz"))
    return out


def _open(path: Path):
    """Open .gz transparently."""
    return gzip.open(path, "rb") if path.suffix == ".gz" else path.open("rb")


def _text(item, tag: str) -> str | None:
    el = item.find(tag)
    return (el.text or "").strip() if el is not None and el.text else None


def _float(item, tag: str) -> float | None:
    s = _text(item, tag)
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_pricefull(path: Path) -> Iterable[dict]:
    """Yield {barcode, name_he, brand, price_ils, price_per_100g_ils} per item.

    Note the gov XML spec uses `<ManufactureName>` (not Manufacturer*) — easy
    to mis-spell and silently lose all brands.
    """
    try:
        with _open(path) as f:
            tree = ET.parse(f)
    except (ET.ParseError, OSError):
        return
    for item in tree.iter("Item"):
        code = _text(item, "ItemCode")
        if not code or not code.isdigit() or len(code) < 7:
            continue
        yield {
            "barcode": code,
            "name_he": _text(item, "ItemName") or "",
            "brand":   _text(item, "ManufactureName"),
            "price_ils": _float(item, "ItemPrice"),
            "price_per_100g_ils": _float(item, "UnitOfMeasurePrice"),
        }


def collect(dest_dir: Path) -> list[dict]:
    """End-to-end: fetch all chains, parse, aggregate prices per barcode.

    We keep the median price across chains (robust to one outlier promotion).
    """
    files = fetch_latest(CHAINS, dest_dir)
    by_code: dict[str, dict] = {}
    prices: dict[str, list[float]] = {}
    unit_prices: dict[str, list[float]] = {}
    for f in files:
        for row in parse_pricefull(f):
            bc = row["barcode"]
            base = by_code.get(bc)
            if not base:
                by_code[bc] = {k: row[k] for k in ("barcode", "name_he", "brand")}
                base = by_code[bc]
            elif not base.get("brand") and row.get("brand"):
                base["brand"] = row["brand"]
            if row.get("price_ils") is not None:
                prices.setdefault(bc, []).append(row["price_ils"])
            if row.get("price_per_100g_ils") is not None:
                unit_prices.setdefault(bc, []).append(row["price_per_100g_ils"])
    # Median price per barcode
    def median(xs: list[float]) -> float:
        xs = sorted(xs)
        n = len(xs)
        return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2
    for bc, item in by_code.items():
        if prices.get(bc):
            item["price_ils"] = round(median(prices[bc]), 2)
        if unit_prices.get(bc):
            item["price_per_100g_ils"] = round(median(unit_prices[bc]), 2)
    return list(by_code.values())
