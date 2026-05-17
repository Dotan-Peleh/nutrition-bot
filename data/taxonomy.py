"""Unified Hebrew taxonomy.

Hand-curated mapping from Tzameret food groups + OFF top-level categories.
The `kind` field controls which Nutri-Score / red-label variant the scorer
applies to a product. ETL maps each source's native category onto the
`category_id` here; the matcher and alternatives module group by it.

Intentionally small in MVP — extend as gaps appear during ETL.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Kind = Literal["solid", "beverage"]


@dataclass(frozen=True)
class Category:
    category_id: str
    parent_id: str | None
    name_he: str
    name_en: str
    kind: Kind


TAXONOMY: list[Category] = [
    # --- top-level groups
    Category("dairy",       None, "מוצרי חלב",         "Dairy",       "solid"),
    Category("beverages",   None, "משקאות",            "Beverages",   "beverage"),
    Category("bakery",      None, "מאפים ולחמים",      "Bakery",      "solid"),
    Category("snacks",      None, "חטיפים",            "Snacks",      "solid"),
    Category("produce",     None, "פירות וירקות",      "Produce",     "solid"),
    Category("meat_fish",   None, "בשר ודגים",         "Meat & Fish", "solid"),
    Category("pantry",      None, "מזווה",             "Pantry",      "solid"),
    Category("frozen",      None, "קפואים",            "Frozen",      "solid"),
    Category("sweets",      None, "ממתקים ודברי מתיקה", "Sweets",      "solid"),
    Category("breakfast",   None, "דגני בוקר וחטיפי דגנים", "Breakfast cereals", "solid"),

    # --- dairy subtree
    Category("milk",        "dairy", "חלב",            "Milk",        "beverage"),
    Category("cottage",     "dairy", "קוטג'",          "Cottage cheese", "solid"),
    Category("yogurt",      "dairy", "יוגורט",         "Yogurt",      "solid"),
    Category("hard_cheese", "dairy", "גבינה קשה",      "Hard cheese", "solid"),
    Category("soft_cheese", "dairy", "גבינה לבנה",     "Soft cheese", "solid"),
    Category("cream",       "dairy", "שמנת",           "Cream",       "solid"),
    Category("butter",      "dairy", "חמאה",           "Butter",      "solid"),
    Category("dairy_dessert", "dairy", "מעדן חלב",     "Dairy dessert", "solid"),
    Category("plant_milk",  "dairy", "חלב צמחי",       "Plant-based milk", "beverage"),

    # --- beverages subtree
    Category("soda",        "beverages", "משקאות מוגזים", "Soft drinks", "beverage"),
    Category("juice",       "beverages", "מיץ",        "Juice",       "beverage"),
    Category("water",       "beverages", "מים",         "Water",       "beverage"),
    Category("energy_drink", "beverages", "משקאות אנרגיה", "Energy drinks", "beverage"),
    Category("coffee_tea",  "beverages", "קפה ותה",     "Coffee & tea", "beverage"),

    # --- bakery
    Category("bread_white", "bakery", "לחם לבן",       "White bread", "solid"),
    Category("bread_whole", "bakery", "לחם מחיטה מלאה", "Whole-grain bread", "solid"),
    Category("pita",        "bakery", "פיתה",          "Pita",        "solid"),
    Category("pastry",      "bakery", "מאפה",          "Pastry",      "solid"),

    # --- snacks
    Category("chips",       "snacks", "צ'יפס וחטיפים מטוגנים", "Chips & fried snacks", "solid"),
    Category("puffed",      "snacks", "חטיפים תפוחים", "Puffed snacks (bamba etc.)", "solid"),
    Category("crackers",    "snacks", "קרקרים",        "Crackers",    "solid"),
    Category("nuts",        "snacks", "אגוזים וזרעים", "Nuts & seeds", "solid"),

    # --- produce
    Category("fruit_fresh", "produce", "פירות טריים",  "Fresh fruit", "solid"),
    Category("veg_fresh",   "produce", "ירקות טריים",  "Fresh vegetables", "solid"),
    Category("legumes",     "produce", "קטניות",       "Legumes",     "solid"),

    # --- meat / fish
    Category("beef",        "meat_fish", "בקר",        "Beef",        "solid"),
    Category("poultry",     "meat_fish", "עוף והודו",  "Poultry",     "solid"),
    Category("fish",        "meat_fish", "דגים",        "Fish",        "solid"),
    Category("processed_meat", "meat_fish", "בשר מעובד", "Processed meat", "solid"),

    # --- pantry
    Category("rice_pasta",  "pantry", "אורז ופסטה",    "Rice & pasta", "solid"),
    Category("oil",         "pantry", "שמן",            "Oil",         "solid"),
    Category("sauce",       "pantry", "רטבים",         "Sauces",      "solid"),
    Category("spread",      "pantry", "ממרחים",         "Spreads",     "solid"),
    Category("canned",      "pantry", "שימורים",        "Canned",      "solid"),

    # --- sweets
    Category("chocolate",   "sweets", "שוקולד",         "Chocolate",   "solid"),
    Category("candy",       "sweets", "ממתקים",         "Candy",       "solid"),
    Category("ice_cream",   "sweets", "גלידה",           "Ice cream",   "solid"),
    Category("cookies",     "sweets", "עוגיות ועוגות",  "Cookies & cakes", "solid"),

    # --- breakfast cereals
    Category("cereal_sugary", "breakfast", "דגני בוקר ממותקים", "Sugary cereal", "solid"),
    Category("cereal_plain",  "breakfast", "דגני בוקר רגילים",  "Plain cereal",  "solid"),
    Category("granola",       "breakfast", "גרנולה",           "Granola",       "solid"),
]


_BY_ID: dict[str, Category] = {c.category_id: c for c in TAXONOMY}


def get(category_id: str) -> Category:
    return _BY_ID[category_id]


def is_beverage(category_id: str | None) -> bool:
    if not category_id:
        return False
    return _BY_ID[category_id].kind == "beverage"


def children(parent_id: str | None) -> list[Category]:
    return [c for c in TAXONOMY if c.parent_id == parent_id]


def all_ids() -> list[str]:
    return [c.category_id for c in TAXONOMY]
