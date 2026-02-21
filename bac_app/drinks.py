"""Drink definitions and alcohol content helpers for BAC tracking.

US standard drink = 14 g ethanol.
"""

from dataclasses import dataclass
from typing import Optional

# US standard drink in grams of pure ethanol.
STANDARD_DRINK_GRAMS = 14.0

# Ethanol density (g/mL) for volume x ABV -> grams.
ETHANOL_DENSITY = 0.789


@dataclass
class DrinkType:
    """A drink category with default ABV and serving size."""

    key: str
    name: str
    abv: float  # e.g. 0.05 for 5%
    default_oz: float  # default serving size in fl oz
    grams_per_serving: float  # grams ethanol per default serving


# Common drink types (US standard servings).
DRINK_TYPES = {
    "beer": DrinkType("beer", "Beer (5%)", 0.05, 12.0, STANDARD_DRINK_GRAMS),
    "wine": DrinkType("wine", "Wine (12%)", 0.12, 5.0, STANDARD_DRINK_GRAMS),
    "liquor": DrinkType("liquor", "Spirit (40%)", 0.40, 1.5, STANDARD_DRINK_GRAMS),
    "seltzer": DrinkType("seltzer", "Hard seltzer (5%)", 0.05, 12.0, STANDARD_DRINK_GRAMS),
}


def grams_from_volume_abv(volume_oz: float, abv: float) -> float:
    """Convert fluid ounces and ABV (0 to 1) to grams of ethanol."""
    # 1 US fl oz ~= 29.5735 mL.
    ml = volume_oz * 29.5735
    return ml * abv * ETHANOL_DENSITY


def grams_from_drink(
    drink_key: str,
    volume_oz: Optional[float] = None,
    count: float = 1.0,
) -> float:
    """Return grams of ethanol for a drink type."""
    dt = DRINK_TYPES.get(drink_key)
    if dt is None:
        return count * STANDARD_DRINK_GRAMS
    if volume_oz is not None:
        return grams_from_volume_abv(volume_oz, dt.abv)
    return count * dt.grams_per_serving


def list_drink_types():
    """Return list of (key, name) for UI dropdowns."""
    return [(d.key, d.name) for d in DRINK_TYPES.values()]