"""Israeli Ministry of Health 'red label' thresholds.

Regulation: any single packaged food crossing a threshold gets a mandatory
front-of-pack red warning label. We mirror those thresholds and apply a fixed
−15 penalty per crossed threshold.
"""
from __future__ import annotations

from typing import Literal

from schemas.products import Nutrients
from schemas.responses import RedLabelFlag

Kind = Literal["solid", "beverage"]

PENALTY_PER_FLAG = 15

# (nutrient_label, attribute, threshold_solid, threshold_beverage, unit)
_RULES = [
    ("sodium",  "sodium_mg", 400.0, 300.0, "mg/100g"),
    ("sugar",   "sugars_g",    5.0,   5.0, "g/100g"),
    ("sat_fat", "sat_fat_g",   4.0,   5.0, "g/100g"),
]


def flags(nutrients: Nutrients, kind: Kind = "solid") -> list[RedLabelFlag]:
    out: list[RedLabelFlag] = []
    for name, attr, t_solid, t_bev, unit in _RULES:
        threshold = t_bev if kind == "beverage" else t_solid
        actual = getattr(nutrients, attr)
        if actual >= threshold:
            out.append(RedLabelFlag(
                nutrient=name,                     # type: ignore[arg-type]
                threshold=threshold,
                actual=round(actual, 2),
                unit=unit.replace("100g", "100ml") if kind == "beverage" else unit,
                penalty=PENALTY_PER_FLAG,
            ))
    return out


def total_penalty(flag_list: list[RedLabelFlag]) -> int:
    return sum(f.penalty for f in flag_list)
