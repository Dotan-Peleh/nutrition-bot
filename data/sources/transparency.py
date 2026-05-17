"""Supermarket transparency XMLs (Shufersal, Rami Levy, Victory).

Thin wrapper around the `il-supermarket-scraper` package. We pull the latest
"PriceFull" file per chain and extract barcode + display name to determine
`available_in_il` for products and to supply Israeli SKU display names.
"""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

CHAINS = ("SHUFERSAL", "RAMI_LEVY", "VICTORY")


def fetch_latest(chain: str, dest_dir: Path) -> list[Path]:
    """Download today's PriceFull XML for the given chain. Returns local paths.

    Heavyweight call — only invoked from the ETL orchestrator. We import the
    library lazily so non-ETL paths don't pay its dependency cost.
    """
    try:
        from il_supermarket_scarper.main import ScarpingTask
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "il-supermarket-scraper not installed. Run: pip install '.[etl]'"
        ) from e

    dest_dir.mkdir(parents=True, exist_ok=True)
    task = ScarpingTask(
        enabled_scrapers=[chain],
        files_types=["PriceFull"],
        dump_folder_name=str(dest_dir),
    )
    task.start()
    return list(dest_dir.rglob("*.xml"))


def parse_pricefull(path: Path) -> Iterable[dict]:
    """Yield {barcode, name_he, brand} per item in a PriceFull XML."""
    import xml.etree.ElementTree as ET
    try:
        tree = ET.parse(path)
    except ET.ParseError:
        return
    for item in tree.iter("Item"):
        code_el = item.find("ItemCode")
        name_el = item.find("ItemName")
        brand_el = item.find("ManufacturerName")
        if code_el is None or not code_el.text:
            continue
        yield {
            "barcode": code_el.text.strip(),
            "name_he": (name_el.text or "").strip() if name_el is not None else "",
            "brand":   (brand_el.text or "").strip() if brand_el is not None else None,
        }


def collect(dest_dir: Path) -> list[dict]:
    """End-to-end: fetch all chains, parse, dedupe by barcode."""
    seen: dict[str, dict] = {}
    for chain in CHAINS:
        try:
            files = fetch_latest(chain, dest_dir / chain.lower())
        except Exception:  # noqa: BLE001
            continue
        for f in files:
            for row in parse_pricefull(f):
                if row["barcode"] not in seen:
                    seen[row["barcode"]] = row
    return list(seen.values())
