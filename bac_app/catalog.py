"""Drink catalog with ABV, serving size, calories, carbs, and sugar.

Values are approximate and can vary by brand/recipe.
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


def _e(
    abv: float,
    oz: float,
    cal: int,
    carb: float,
    sugar: float,
    name: str,
    cat: str,
    bid: str,
    brand: Optional[str] = None,
) -> CatalogEntry:
    return CatalogEntry(
        id=bid,
        name=name,
        category=cat,
        abv=abv,
        serving_oz=oz,
        calories=cal,
        carbs_g=carb,
        sugar_g=sugar,
        brand=brand,
    )


CATALOG: List[CatalogEntry] = [
    # Light / domestic beers
    _e(0.042, 12, 110, 6.6, 0, "Bud Light", "beer", "bud-light", "Budweiser"),
    _e(0.042, 12, 102, 5.0, 0, "Coors Light", "beer", "coors-light", "Coors"),
    _e(0.04, 12, 96, 3.2, 0, "Michelob Ultra", "beer", "michelob-ultra", "Michelob"),
    _e(0.042, 12, 99, 3.9, 0, "Miller Lite", "beer", "miller-lite", "Miller"),
    _e(0.04, 12, 95, 2.6, 0, "Corona Light", "beer", "corona-light", "Corona"),
    _e(0.051, 12, 149, 10.6, 0, "Corona Extra", "beer", "corona-extra", "Corona"),
    _e(0.05, 12, 145, 13, 0, "Budweiser", "beer", "budweiser", "Budweiser"),
    _e(0.047, 12, 153, 12.6, 0, "Miller High Life", "beer", "miller-high-life", "Miller"),
    _e(0.05, 12, 153, 12, 0, "Pabst Blue Ribbon", "beer", "pbr", "PBR"),
    _e(0.06, 12, 175, 14, 0, "Modelo Especial", "beer", "modelo-especial", "Modelo"),
    _e(0.055, 12, 170, 13, 0, "Pacifico", "beer", "pacifico", "Pacifico"),
    _e(0.05, 12, 142, 11, 0, "Stella Artois", "beer", "stella-artois", "Stella Artois"),
    _e(0.045, 12, 140, 10, 0, "Blue Moon", "beer", "blue-moon", "Blue Moon"),
    _e(0.04, 12, 105, 4, 0, "Heineken 0.0", "beer", "heineken-00", "Heineken"),
    _e(0.05, 12, 150, 13, 0, "Heineken", "beer", "heineken", "Heineken"),
    _e(0.055, 12, 170, 15, 0, "Sam Adams Boston Lager", "beer", "sam-adams-lager", "Sam Adams"),
    # IPA / craft / stronger beer
    _e(0.055, 12, 170, 15, 0, "IPA (typical)", "beer", "ipa-typical"),
    _e(0.065, 12, 200, 18, 0, "Double IPA", "beer", "double-ipa"),
    _e(0.068, 12, 195, 17, 0, "Hazy IPA", "beer", "hazy-ipa"),
    _e(0.052, 12, 180, 16, 0, "Sierra Nevada Pale Ale", "beer", "sierra-pale", "Sierra Nevada"),
    _e(0.056, 12, 175, 14, 0, "Lagunitas IPA", "beer", "lagunitas-ipa", "Lagunitas"),
    _e(0.08, 12, 230, 20, 0, "Imperial Stout", "beer", "imperial-stout"),
    _e(0.065, 12, 185, 14, 0, "Belgian Ale", "beer", "belgian-ale"),
    # Hard seltzers / canned cocktails
    _e(0.05, 12, 100, 2, 0, "White Claw (5%)", "seltzer", "white-claw-5", "White Claw"),
    _e(0.05, 12, 100, 1, 0, "Truly", "seltzer", "truly", "Truly"),
    _e(0.05, 12, 95, 0, 0, "High Noon", "seltzer", "high-noon", "High Noon"),
    _e(0.045, 12, 90, 0, 0, "Vizzy", "seltzer", "vizzy", "Vizzy"),
    _e(0.05, 12, 110, 4, 1, "Bud Light Seltzer", "seltzer", "bud-seltzer", "Bud Light"),
    _e(0.05, 12, 110, 2, 0, "Topo Chico Hard Seltzer", "seltzer", "topo-chico-seltzer", "Topo Chico"),
    _e(0.045, 12, 100, 2, 0, "Truly Lemonade", "seltzer", "truly-lemonade", "Truly"),
    _e(0.045, 12, 100, 2, 0, "White Claw Surge", "seltzer", "white-claw-surge", "White Claw"),
    _e(0.06, 12, 150, 12, 9, "Canned Vodka Soda", "seltzer", "canned-vodka-soda"),
    # Wine / bubbly
    _e(0.12, 5, 120, 4, 1, "Red wine (5 oz)", "wine", "red-wine"),
    _e(0.12, 5, 120, 4, 1.5, "White wine (5 oz)", "wine", "white-wine"),
    _e(0.12, 5, 125, 4, 2, "Rose (5 oz)", "wine", "rose"),
    _e(0.09, 5, 90, 4, 1.5, "Champagne (5 oz)", "wine", "champagne"),
    _e(0.12, 8, 180, 5, 3, "Wine spritzer (8 oz)", "wine", "wine-spritzer"),
    _e(0.13, 5, 125, 3.8, 1.2, "Cabernet Sauvignon (5 oz)", "wine", "cabernet"),
    _e(0.12, 5, 121, 3.8, 1.4, "Pinot Noir (5 oz)", "wine", "pinot-noir"),
    _e(0.125, 5, 122, 4.2, 1.6, "Merlot (5 oz)", "wine", "merlot"),
    _e(0.13, 5, 123, 3.9, 1.3, "Sauvignon Blanc (5 oz)", "wine", "sauvignon-blanc"),
    _e(0.12, 5, 121, 4.0, 1.5, "Chardonnay (5 oz)", "wine", "chardonnay"),
    _e(0.12, 5, 122, 4.1, 1.8, "Pinot Grigio (5 oz)", "wine", "pinot-grigio"),
    _e(0.11, 5, 118, 4.5, 2.2, "Riesling (5 oz)", "wine", "riesling"),
    _e(0.11, 5, 117, 4.5, 2.5, "Moscato (5 oz)", "wine", "moscato"),
    _e(0.10, 5, 95, 5, 4, "Prosecco (5 oz)", "wine", "prosecco"),
    # Liquor shots (1.5 oz)
    _e(0.40, 1.5, 96, 0, 0, "Vodka (1.5 oz)", "liquor", "vodka"),
    _e(0.40, 1.5, 96, 0, 0, "Rum (1.5 oz)", "liquor", "rum"),
    _e(0.40, 1.5, 96, 0, 0, "Tequila (1.5 oz)", "liquor", "tequila"),
    _e(0.40, 1.5, 96, 0, 0, "Whiskey (1.5 oz)", "liquor", "whiskey"),
    _e(0.40, 1.5, 96, 0, 0, "Gin (1.5 oz)", "liquor", "gin"),
    _e(0.40, 1.5, 96, 0, 0, "Bourbon (1.5 oz)", "liquor", "bourbon"),
    _e(0.40, 1.5, 96, 0, 0, "Scotch (1.5 oz)", "liquor", "scotch"),
    _e(0.40, 1.5, 96, 0, 0, "Brandy (1.5 oz)", "liquor", "brandy"),
    _e(0.40, 1.5, 105, 0, 0, "Jack Daniel's", "liquor", "jack-daniels", "Jack Daniel's"),
    _e(0.35, 1.5, 97, 0, 11, "Fireball (1.5 oz)", "liquor", "fireball", "Fireball"),
    _e(0.30, 1.5, 103, 0, 9, "Jagermeister (1.5 oz)", "liquor", "jagermeister", "Jagermeister"),
    _e(0.35, 1.5, 104, 5, 5, "Malibu Coconut Rum (1.5 oz)", "liquor", "malibu", "Malibu"),
    _e(0.20, 1.5, 95, 11, 11, "Peach Schnapps (1.5 oz)", "liquor", "peach-schnapps"),
    # Classic cocktails (approximate per drink)
    _e(0.18, 4, 180, 8, 7, "Margarita", "cocktail", "margarita"),
    _e(0.15, 4, 160, 6, 0, "Vodka soda", "cocktail", "vodka-soda"),
    _e(0.20, 4, 200, 15, 12, "Long Island Iced Tea", "cocktail", "long-island"),
    _e(0.14, 5, 220, 25, 20, "Mai Tai", "cocktail", "mai-tai"),
    _e(0.12, 6, 180, 12, 8, "Moscow Mule", "cocktail", "moscow-mule"),
    _e(0.15, 4, 150, 10, 10, "Whiskey Coke", "cocktail", "whiskey-coke"),
    _e(0.10, 12, 140, 14, 0, "Beer + shot (boilermaker)", "cocktail", "boilermaker"),
    _e(0.18, 3.5, 150, 1, 1, "Martini", "cocktail", "martini"),
    _e(0.15, 3.5, 175, 11, 11, "Cosmopolitan", "cocktail", "cosmopolitan"),
    _e(0.16, 3, 165, 7, 6, "Manhattan", "cocktail", "manhattan"),
    _e(0.16, 3, 165, 7, 7, "Old Fashioned", "cocktail", "old-fashioned"),
    _e(0.12, 8, 170, 14, 12, "Mojito", "cocktail", "mojito"),
    _e(0.15, 6, 210, 18, 16, "Daiquiri", "cocktail", "daiquiri"),
    _e(0.14, 6, 190, 16, 12, "Paloma", "cocktail", "paloma"),
    _e(0.14, 6, 210, 24, 21, "Tequila Sunrise", "cocktail", "tequila-sunrise"),
    _e(0.16, 6, 230, 18, 15, "Pina Colada", "cocktail", "pina-colada"),
    _e(0.13, 7, 220, 24, 22, "Sex on the Beach", "cocktail", "sex-on-beach"),
    _e(0.10, 7, 190, 23, 18, "Aperol Spritz", "cocktail", "aperol-spritz"),
    _e(0.12, 7, 180, 20, 15, "Gin and Tonic", "cocktail", "gin-tonic"),
    _e(0.16, 4, 185, 6, 5, "Negroni", "cocktail", "negroni"),
    _e(0.17, 2.5, 135, 2, 2, "Shot + chaser combo", "cocktail", "shot-chaser"),
    # Other common bar options
    _e(0.045, 12, 170, 18, 15, "Hard cider", "other", "hard-cider"),
    _e(0.07, 12, 240, 25, 20, "Stronger hard cider", "other", "hard-cider-strong"),
    _e(0.05, 12, 155, 13, 10, "Hard lemonade", "other", "hard-lemonade"),
    _e(0.06, 12, 220, 24, 18, "Hard tea", "other", "hard-tea"),
    _e(0.07, 8, 250, 30, 24, "Frozen cocktail", "other", "frozen-cocktail"),
    _e(0.09, 16, 260, 28, 22, "Large mixed drink", "other", "large-mixed-drink"),
    _e(0.05, 10, 130, 10, 8, "Sangria (10 oz)", "other", "sangria"),
]

_CATALOG_BY_ID: Dict[str, CatalogEntry] = {e.id: e for e in CATALOG}


def get_entry(catalog_id: str) -> Optional[CatalogEntry]:
    return _CATALOG_BY_ID.get(catalog_id)


def grams_and_nutrition(catalog_id: str, count: float = 1.0) -> tuple[float, int, float, float]:
    """Return (grams_ethanol, calories, carbs_g, sugar_g) for `count` servings."""
    entry = get_entry(catalog_id)
    if not entry:
        return (count * STANDARD_DRINK_GRAMS, 0, 0.0, 0.0)

    grams = grams_from_volume_abv(entry.serving_oz * count, entry.abv)
    return (
        grams,
        int(entry.calories * count),
        entry.carbs_g * count,
        entry.sugar_g * count,
    )


def _entry_dict(entry: CatalogEntry) -> dict:
    return {
        "id": entry.id,
        "name": entry.name,
        "abv": round(entry.abv * 100, 1),
        "serving_oz": entry.serving_oz,
        "calories": entry.calories,
        "carbs_g": entry.carbs_g,
        "sugar_g": entry.sugar_g,
        "brand": entry.brand or "",
    }


def list_by_category() -> Dict[str, List[dict]]:
    """Group catalog entries by category for the UI."""
    out: Dict[str, List[dict]] = {}
    for entry in CATALOG:
        out.setdefault(entry.category, []).append(_entry_dict(entry))
    return out


def list_all_flat() -> List[dict]:
    """Return all catalog entries as a flat list for dropdowns."""
    return [{**_entry_dict(entry), "category": entry.category} for entry in CATALOG]
