"""Product matcher: parsed shopping list item → canonical product.

MVP: stages 1–2 only (exact + rapidfuzz lexical). Semantic + LLM disambig are
Phase 3b, behind a feature flag.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import duckdb
from rapidfuzz import fuzz, process

from core.hebrew import normalize


@dataclass(frozen=True)
class ParsedItem:
    raw: str
    qty: float = 1.0
    unit: str = "unit"
    brand: str | None = None
    category_hint: str | None = None
    attributes: tuple[tuple[str, str | float], ...] = ()
    confidence: float = 1.0

    @property
    def query_text(self) -> str:
        bits = [self.raw]
        if self.brand:
            bits.append(self.brand)
        return " ".join(bits)


@dataclass(frozen=True)
class MatchResult:
    product_id: str | None
    confidence: float
    matched_via: str          # 'barcode' | 'exact' | 'fuzzy' | 'none'
    name_he: str | None = None
    brand: str | None = None
    category_id: str | None = None


FUZZY_CUTOFF = 88.0


def _all_candidates(con: duckdb.DuckDBPyConnection, brand: str | None,
                    category_hint: str | None) -> list[tuple[str, str, str | None, str | None]]:
    """Return (canonical_id, name_he, brand, category_id) candidate rows.

    Prefilter on brand or category if available, fall back to full table.
    Result rows are also augmented with rows from `aliases` for the same id.
    """
    where = []
    params: list = []
    if brand:
        where.append("LOWER(brand) = ?")
        params.append(brand.lower())
    if category_hint:
        where.append("category_id = ?")
        params.append(category_hint)

    base_sql = "SELECT canonical_id, name_he, brand, category_id FROM products"
    if where:
        sql = f"{base_sql} WHERE {' OR '.join(where)}"
    else:
        sql = base_sql
    rows = con.execute(sql, params).fetchall()

    # Add alias rows so fuzzy can hit synonyms.
    alias_rows = con.execute(
        "SELECT p.canonical_id, a.alias_he, p.brand, p.category_id "
        "FROM aliases a JOIN products p ON a.product_id = p.canonical_id"
    ).fetchall()
    return rows + alias_rows


def match(
    item: ParsedItem,
    con: duckdb.DuckDBPyConnection,
) -> MatchResult:
    q_norm = normalize(item.query_text)
    if not q_norm:
        return MatchResult(None, 0.0, "none")

    # Stage 1: exact canonical-name match (after normalization)
    exact = con.execute(
        "SELECT canonical_id, name_he, brand, category_id FROM products "
        "WHERE LOWER(name_he) = ? LIMIT 1",
        [q_norm],
    ).fetchone()
    if exact:
        return MatchResult(
            product_id=exact[0], confidence=1.0, matched_via="exact",
            name_he=exact[1], brand=exact[2], category_id=exact[3],
        )

    # Stage 2: rapidfuzz over candidate set
    candidates = _all_candidates(con, item.brand, item.category_hint)
    if not candidates:
        return MatchResult(None, 0.0, "none")

    choices = {i: normalize(f"{row[1]} {row[2] or ''}") for i, row in enumerate(candidates)}
    best = process.extractOne(q_norm, choices, scorer=fuzz.WRatio, score_cutoff=FUZZY_CUTOFF)
    if best is None:
        return MatchResult(None, 0.0, "none")
    _, score_v, idx = best
    row = candidates[idx]
    return MatchResult(
        product_id=row[0],
        confidence=round(score_v / 100.0, 3),
        matched_via="fuzzy",
        name_he=row[1],
        brand=row[2],
        category_id=row[3],
    )


# Convenience cache for repeated identical lookups in a single process.
@lru_cache(maxsize=10_000)
def _cache_key(raw: str, brand: str | None, category_hint: str | None) -> str:
    return f"{normalize(raw)}|{brand or ''}|{category_hint or ''}"
