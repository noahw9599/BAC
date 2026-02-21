"""
Drink catalog: brands with ABV, serving size, calories, carbs, sugar.
College-friendly list; accuracy varies by brand/source.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from bac_app.drinks import grams_from_volume_abv

STANDARD_DRINK_GRAMS = 14.0


@dataclass
class CatalogEntry:
    id: str
    name: str
    category: str  # beer, seltzer, wine, liquor, cocktail, other
    abv: float
    serving_oz: float
    calories: int
    carbs_g: float
    sugar_g: float
    brand: Optional[str] = None


def _e(abv: float, oz: float, cal: int, carb: float, sugar: float, name: str, cat: str, bid: str, brand: Optional[str] = None) -> CatalogEntry:
    return CatalogEntry(id=bid, name=name, category=cat, abv=abv, serving_oz=oz, calories=cal, carbs_g=carb, sugar_g=sugar, brand=brand)


# Curated list: common college drinks (approximate values; brands vary). sugar_g = grams sugar per serving.
CATALOG: List[CatalogEntry] = [
    # Light beers
    _e(0.042, 12, 110, 6.6, 0, "Bud Light", "beer", "bud-light", "Budweiser"),
    _e(0.042, 12, 102, 5.0, 0, "Coors Light", "beer", "coors-light", "Coors"),
    _e(0.04, 12, 96, 3.2, 0, "Michelob Ultra", "beer", "michelob-ultra", "Michelob"),
    _e(0.042, 12, 99, 3.9, 0, "Miller Lite", "beer", "miller-lite", "Miller"),
    _e(0.04, 12, 95, 2.6, 0, "Corona Light", "beer", "corona-light", "Corona"),
    _e(0.045, 12, 140, 10, 0, "Blue Moon", "beer", "blue-moon", "Blue Moon"),
    _e(0.05, 12, 145, 13, 0, "Budweiser", "beer", "budweiser", "Budweiser"),
    _e(0.051, 12, 149, 10.6, 0, "Corona Extra", "beer", "corona-extra", "Corona"),
    # IPAs / craft
    _e(0.055, 12, 170, 15, 0, "IPA (typical)", "beer", "ipa-typical", None),
    _e(0.065, 12, 200, 18, 0, "Double IPA", "beer", "double-ipa", None),
    _e(0.052, 12, 180, 16, 0, "Sierra Nevada Pale Ale", "beer", "sierra-pale", "Sierra Nevada"),
    # Hard seltzers
    _e(0.05, 12, 100, 2, 0, "White Claw (5%)", "seltzer", "white-claw-5", "White Claw"),
    _e(0.07, 12, 130, 2, 0, "White Claw 70", "seltzer", "white-claw-70", "White Claw"),
    _e(0.05, 12, 100, 1, 0, "Truly", "seltzer", "truly", "Truly"),
    _e(0.05, 12, 95, 0, 0, "High Noon", "seltzer", "high-noon", "High Noon"),
    _e(0.045, 12, 90, 0, 0, "Vizzy", "seltzer", "vizzy", "Vizzy"),
    _e(0.05, 12, 110, 4, 1, "Bud Light Seltzer", "seltzer", "bud-seltzer", "Bud Light"),
    # Wine
    _e(0.12, 5, 120, 4, 1, "Red wine (5 oz)", "wine", "red-wine", None),
    _e(0.12, 5, 120, 4, 1.5, "White wine (5 oz)", "wine", "white-wine", None),
    _e(0.12, 5, 125, 4, 2, "Rosé (5 oz)", "wine", "rose", None),
    _e(0.09, 5, 90, 4, 1.5, "Champagne (5 oz)", "wine", "champagne", None),
    _e(0.12, 8, 180, 5, 3, "Wine spritzer (8 oz)", "wine", "wine-spritzer", None),
    # Liquor (1.5 oz shot)
    _e(0.40, 1.5, 96, 0, 0, "Vodka (1.5 oz)", "liquor", "vodka", None),
    _e(0.40, 1.5, 96, 0, 0, "Rum (1.5 oz)", "liquor", "rum", None),
    _e(0.40, 1.5, 96, 0, 0, "Tequila (1.5 oz)", "liquor", "tequila", None),
    _e(0.40, 1.5, 96, 0, 0, "Whiskey (1.5 oz)", "liquor", "whiskey", None),
    _e(0.40, 1.5, 105, 0, 0, "Jack Daniel's", "liquor", "jack-daniels", "Jack Daniel's"),
    _e(0.35, 1.5, 97, 0, 11, "Fireball (1.5 oz)", "liquor", "fireball", "Fireball"),
    # Cocktails (approximate per drink)
    _e(0.18, 4, 180, 8, 7, "Margarita", "cocktail", "margarita", None),
    _e(0.15, 4, 160, 6, 0, "Vodka soda", "cocktail", "vodka-soda", None),
    _e(0.20, 4, 200, 15, 12, "Long Island Iced Tea", "cocktail", "long-island", None),
    _e(0.14, 5, 220, 25, 20, "Mai Tai", "cocktail", "mai-tai", None),
    _e(0.12, 6, 180, 12, 8, "Moscow Mule", "cocktail", "moscow-mule", None),
    _e(0.15, 4, 150, 10, 10, "Whiskey Coke", "cocktail", "whiskey-coke", None),
    _e(0.10, 12, 140, 14, 0, "Beer + shot (boilermaker)", "cocktail", "boilermaker", None),
]

_CATALOG_BY_ID: Dict[str, CatalogEntry] = {e.id: e for e in CATALOG}


def get_entry(catalog_id: str) -> Optional[CatalogEntry]:
    return _CATALOG_BY_ID.get(catalog_id)


def grams_and_nutrition(catalog_id: str, count: float = 1.0) -> tuple[float, int, float, float]:
    """Returns (grams_ethanol, total_calories, total_carbs_g, total_sugar_g) for count servings."""
    e = get_entry(catalog_id)
    if not e:
        return (count * STANDARD_DRINK_GRAMS, 0, 0.0, 0.0)
    g = grams_from_volume_abv(e.serving_oz * count, e.abv)
    return (g, int(e.calories * count), e.carbs_g * count, e.sugar_g * count)


def list_by_category() -> Dict[str, List[dict]]:
    """Group catalog by category for UI. Each entry as dict with id, name, abv, serving_oz, calories, carbs_g, sugar_g, brand."""
    out: Dict[str, List[dict]] = {}
    for e in CATALOG:
        out.setdefault(e.category, []).append({
            "id": e.id,
            "name": e.name,
            "abv": round(e.abv * 100, 1),
            "serving_oz": e.serving_oz,
            "calories": e.calories,
            "carbs_g": e.carbs_g,
            "sugar_g": e.sugar_g,
            "brand": e.brand or "",
        })
    return out


def list_all_flat() -> List[dict]:
    """All entries as list of dicts with category for single dropdown."""
    return [
        {"id": e.id, "name": e.name, "category": e.category, "abv": round(e.abv * 100, 1), "serving_oz": e.serving_oz, "calories": e.calories, "carbs_g": e.carbs_g, "sugar_g": e.sugar_g}
        for e in CATALOG
    ]
