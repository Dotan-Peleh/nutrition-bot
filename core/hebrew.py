"""Hebrew text normalization for matching.

Strip niqqud (vowel marks + cantillation), fold final-letter pairs to base
forms (ם→מ, ך→כ, ן→נ, ץ→צ, ף→פ), strip punctuation typically used in Hebrew
product names (geresh '), and collapse whitespace.
"""
from __future__ import annotations

import re
import unicodedata

# Hebrew niqqud + cantillation range
_NIQQUD_RE = re.compile(r"[֑-ׇ]")
_FINAL_MAP = str.maketrans("םןךץף", "מנכצפ")
_PUNCT_RE  = re.compile(r"['\"׳״.,!?\-/\(\)\[\]]")
_WS_RE     = re.compile(r"\s+")


def normalize(text: str) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFC", text)
    t = _NIQQUD_RE.sub("", t)
    t = t.translate(_FINAL_MAP)
    t = _PUNCT_RE.sub(" ", t)
    t = _WS_RE.sub(" ", t).strip()
    return t.lower()


_NUMERIC_REPLACEMENTS = {
    "½": "0.5",
    "¼": "0.25",
    "¾": "0.75",
    "⅓": "0.33",
    "⅔": "0.66",
}


def normalize_numerics(text: str) -> str:
    """Replace unicode fractions in text. Used by the parser pre-pass."""
    for src, dst in _NUMERIC_REPLACEMENTS.items():
        text = text.replace(src, dst)
    return text
