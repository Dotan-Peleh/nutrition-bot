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
    # Fallback: if a brand/category prefilter returned nothing (common when the
    # catalog has NULL category_ids), widen to the full products table so fuzzy
    # still has something to match against.
    if where and not rows:
        rows = con.execute(base_sql).fetchall()

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

    # Stage 1: exact canonical-name match. Prefer products we can actually
    # score — if multiple rows share a name (common: same generic name lives
    # in Tzameret with full nutrition AND in OFF/transparency with thin data),
    # the scoreable one wins. We approximate "scoreable" via a JOIN against
    # nutrients(sodium_mg > 0).
    exact = con.execute(
        "SELECT p.canonical_id, p.name_he, p.brand, p.category_id "
        "FROM products p "
        "LEFT JOIN nutrients n ON n.product_id = p.canonical_id "
        "  AND n.nutrient_code = 'sodium_mg' AND n.value > 0 "
        "WHERE LOWER(p.name_he) = ? "
        "ORDER BY (n.value IS NOT NULL) DESC, "
        "  CASE p.source WHEN 'tzameret' THEN 0 WHEN 'off' THEN 1 ELSE 2 END "
        "LIMIT 1",
        [q_norm],
    ).fetchone()
    if exact:
        return MatchResult(
            product_id=exact[0], confidence=1.0, matched_via="exact",
            name_he=exact[1], brand=exact[2], category_id=exact[3],
        )

    # Stage 2: two-pass rapidfuzz. First try only products with real nutrition
    # data (sourceable, with energy + a negative nutrient). If that misses,
    # fall back to all candidates so we still surface a name match (will be
    # flagged downstream as "no nutrition data").
    # A product is "scoreable" if we know its sodium (the strongest Nutri-Score
    # signal in IL) AND at least one of sat_fat / sugars. We don't require
    # energy_kj because Tzameret only ships kcal and the loader doesn't yet
    # back-fill kJ.
    scoreable_ids = {
        r[0] for r in con.execute("""
            SELECT DISTINCT p.canonical_id
            FROM products p
            JOIN nutrients sodium ON sodium.product_id = p.canonical_id
              AND sodium.nutrient_code='sodium_mg' AND sodium.value > 0
            JOIN nutrients other ON other.product_id = p.canonical_id
              AND other.nutrient_code IN ('sat_fat_g','sugars_g') AND other.value > 0
        """).fetchall()
    }

    candidates = _all_candidates(con, item.brand, item.category_hint)
    if not candidates:
        return MatchResult(None, 0.0, "none")

    scoreable_candidates = [c for c in candidates if c[0] in scoreable_ids]
    chosen_row = None
    chosen_score = 0.0
    if scoreable_candidates:
        sc_choices = {i: normalize(f"{r[1]} {r[2] or ''}")
                      for i, r in enumerate(scoreable_candidates)}
        # On the scoreable pool we use token_set_ratio so that short Hebrew
        # queries ("קוטג 5%") still hit verbose Tzameret canonical names
        # ("גבינת קוטג' 5% שומן, תנובה"). Cutoff bumped to 80 to keep precision.
        best = process.extractOne(q_norm, sc_choices,
                                  scorer=fuzz.token_set_ratio, score_cutoff=80)
        if best:
            _, chosen_score, idx = best
            chosen_row = scoreable_candidates[idx]

    if chosen_row is None:
        # Fallback: full pool (may include transparency-only rows w/o nutrition)
        all_choices = {i: normalize(f"{r[1]} {r[2] or ''}")
                       for i, r in enumerate(candidates)}
        best = process.extractOne(q_norm, all_choices,
                                  scorer=fuzz.WRatio, score_cutoff=FUZZY_CUTOFF)
        if best is None:
            return MatchResult(None, 0.0, "none")
        _, chosen_score, idx = best
        chosen_row = candidates[idx]
    score_v, row = chosen_score, chosen_row
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
