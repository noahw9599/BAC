"""
Drinking session: profile, drink log (with nutrition), BAC and hangover helpers.
Time: hours from "now" (0); negative = in the past.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from bac_app.drinks import grams_from_drink
from bac_app import calculations
from bac_app.catalog import grams_and_nutrition

# Event: (hours_from_now, grams_ethanol, calories, carbs_g, sugar_g)
EventTuple = Tuple[float, float, int, float, float]


@dataclass
class Session:
    weight_lb: float
    is_male: bool = True
    start_time_hours: float = 0.0
    _events: List[EventTuple] = field(default_factory=list)

    def _events_bac(self) -> List[Tuple[float, float]]:
        return [(e[0], e[1]) for e in self._events]

    @property
    def events_bac(self) -> List[Tuple[float, float]]:
        return self._events_bac()

    def add_drink(self, hours_from_start: float, drink_key: str, count: float = 1.0) -> None:
        g = grams_from_drink(drink_key, volume_oz=None, count=count)
        self._events.append((hours_from_start, g, 0, 0.0, 0.0))

    def add_drink_ago(self, hours_ago: float, drink_key: str, count: float = 1.0) -> None:
        self.add_drink(-hours_ago, drink_key, count)

    def add_drink_catalog(self, hours_ago: float, catalog_id: str, count: float = 1.0) -> None:
        g, cal, carb, sugar = grams_and_nutrition(catalog_id, count)
        self._events.append((-hours_ago, g, cal, carb, sugar))

    def add_drink_grams(self, hours_from_start: float, grams: float, calories: int = 0, carbs_g: float = 0, sugar_g: float = 0) -> None:
        self._events.append((hours_from_start, grams, calories, carbs_g, sugar_g))

    @property
    def events(self) -> List[Tuple[float, float]]:
        return sorted(self.events_bac, key=lambda x: x[0])

    @property
    def events_full(self) -> List[EventTuple]:
        return sorted(self._events, key=lambda x: x[0])

    @property
    def total_calories(self) -> int:
        return sum(e[2] for e in self._events)

    @property
    def total_carbs_g(self) -> float:
        return sum(e[3] for e in self._events)

    @property
    def total_sugar_g(self) -> float:
        return sum(e[4] for e in self._events)

    def bac_now(self, current_hours: Optional[float] = None) -> float:
        if current_hours is None:
            current_hours = max((t for t, _ in self.events_bac), default=0.0)
        return calculations.bac_at_time(current_hours, self.events_bac, self.weight_lb, self.is_male)

    def curve(
        self,
        step_hours: float = 0.25,
        start_hours: Optional[float] = None,
        max_hours: Optional[float] = None,
    ):
        return calculations.bac_curve(
            self.events_bac,
            self.weight_lb,
            self.is_male,
            step_hours=step_hours,
            start_hours=start_hours,
            max_hours=max_hours,
        )

    def hours_until_sober(self) -> float:
        return calculations.time_to_sober(self.events_bac, self.weight_lb, self.is_male)

    def hours_until_sober_from_now(self) -> float:
        if not self._events:
            return 0.0
        curve = self.curve(step_hours=0.25, start_hours=0.0, max_hours=24.0)
        for t, bac in curve:
            if bac <= 0.001:
                return round(t, 2)
        return 24.0
