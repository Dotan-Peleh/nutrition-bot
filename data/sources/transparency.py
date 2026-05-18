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


def parse_pricefull(path: Path) -> Iterable[dict]:
    """Yield {barcode, name_he, brand} per item in a PriceFull XML."""
    try:
        with _open(path) as f:
            tree = ET.parse(f)
    except (ET.ParseError, OSError):
        return
    for item in tree.iter("Item"):
        code_el = item.find("ItemCode")
        name_el = item.find("ItemName")
        brand_el = item.find("ManufacturerName")
        if code_el is None or not code_el.text:
            continue
        code = code_el.text.strip()
        # Skip internal store codes (transparency law mandates real barcodes 7+ digits)
        if not code.isdigit() or len(code) < 7:
            continue
        yield {
            "barcode": code,
            "name_he": (name_el.text or "").strip() if name_el is not None else "",
            "brand":   (brand_el.text or "").strip() if brand_el is not None else None,
        }


def collect(dest_dir: Path) -> list[dict]:
    """End-to-end: fetch all chains, parse, dedupe by barcode."""
    files = fetch_latest(CHAINS, dest_dir)
    seen: dict[str, dict] = {}
    for f in files:
        for row in parse_pricefull(f):
            bc = row["barcode"]
            if bc not in seen or (not seen[bc].get("brand") and row.get("brand")):
                seen[bc] = row
    return list(seen.values())
