"""Hebrew shopping-list parser.

Production path: one Claude Haiku call with prompt-cached system message
(taxonomy + brand list) returning a structured JSON array. Test/offline path:
regex tokenizer that splits on newlines/commas and pulls out qty + unit.
"""
from __future__ import annotations

import json
import os
import re
from collections.abc import Sequence
from dataclasses import asdict

from core.hebrew import normalize_numerics
from core.matcher import ParsedItem

# Numeric quantity at start of line: "2", "0.5", "1.5"
_QTY_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s+(.*)$")

# Common Hebrew brand fragments that often appear inline. Used only by the
# offline fallback parser; the LLM path uses the full brand list from DB.
_INLINE_BRANDS = [
    "תנובה", "טרה", "שטראוס", "אסם", "תלמה", "עלית", "יטבתה",
    "מילר", "אוסם", "פרי הגליל", "צבר",
]


def _split(text: str) -> list[str]:
    parts = re.split(r"[\n,;]+", text)
    return [p.strip() for p in parts if p.strip()]


def _parse_line_offline(line: str) -> ParsedItem:
    line = normalize_numerics(line)
    qty = 1.0
    m = _QTY_RE.match(line)
    if m:
        qty = float(m.group(1))
        line = m.group(2)
    brand: str | None = None
    for b in _INLINE_BRANDS:
        if b in line:
            brand = b
            break
    return ParsedItem(raw=line, qty=qty, brand=brand)


def parse_offline(items: Sequence[str] | str) -> list[ParsedItem]:
    """Pure-Python parser used in tests + as a fallback when no API key."""
    if isinstance(items, str):
        lines = _split(items)
    else:
        lines = [normalize_numerics(s) for s in items]
    return [_parse_line_offline(line) for line in lines]


# --- LLM path -----------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = """\
You are a Hebrew shopping-list parser for an Israeli grocery health-scoring app.
For each line, extract:
  raw: original text
  qty: number (default 1)
  unit: 'unit' | 'kg' | 'g' | 'l' | 'ml'
  brand: brand name in Hebrew if present, else null
  category_hint: one of {category_ids}
  attributes: object with optional fat_pct, sugar_free (bool), whole_grain (bool)
  confidence: 0..1

Return ONLY a JSON array. No prose.
"""


def _build_system_prompt(category_ids: list[str]) -> str:
    return _SYSTEM_PROMPT_TEMPLATE.format(category_ids=category_ids)


def parse_with_claude(
    items: Sequence[str] | str,
    category_ids: list[str],
    *,
    client=None,
    model: str = "claude-haiku-4-5-20251001",
) -> list[ParsedItem]:
    """LLM-backed parser. `client` must be an `anthropic.Anthropic` instance.

    Returns the same `ParsedItem` shape as the offline parser, so downstream
    code is parser-agnostic.
    """
    if client is None:  # pragma: no cover — import only when needed
        import anthropic
        client = anthropic.Anthropic()

    raw_text = items if isinstance(items, str) else "\n".join(items)
    raw_text = normalize_numerics(raw_text)

    resp = client.messages.create(
        model=model,
        max_tokens=2048,
        system=[{
            "type": "text",
            "text": _build_system_prompt(category_ids),
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": raw_text}],
    )
    text = resp.content[0].text  # type: ignore[union-attr]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # The model occasionally wraps in ```json fences — strip them.
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
        parsed = json.loads(text)

    out: list[ParsedItem] = []
    for it in parsed:
        attrs = it.get("attributes") or {}
        out.append(ParsedItem(
            raw=it.get("raw", ""),
            qty=float(it.get("qty", 1)),
            unit=it.get("unit", "unit"),
            brand=it.get("brand"),
            category_hint=it.get("category_hint"),
            attributes=tuple(sorted(attrs.items())),
            confidence=float(it.get("confidence", 0.8)),
        ))
    return out


def parse(items: Sequence[str] | str, category_ids: list[str] | None = None) -> list[ParsedItem]:
    """Default entry: use Claude if `ANTHROPIC_API_KEY` is set, else offline."""
    if os.environ.get("ANTHROPIC_API_KEY") and category_ids:
        try:
            return parse_with_claude(items, category_ids)
        except Exception:  # noqa: BLE001 — fall back rather than 500 the request
            pass
    return parse_offline(items)


def parsed_item_to_dict(p: ParsedItem) -> dict:
    """Helper for tests / debug logging."""
    return {**asdict(p), "attributes": dict(p.attributes)}
