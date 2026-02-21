"""BAC calculations using Widmark-style rise and linear elimination.

Model:
- Rise: BAC = [grams / (body_weight_g * r)] * 100
- r = 0.68 (male), 0.55 (female)
- Elimination: 0.015 BAC percentage points per hour
"""

from typing import List, Optional, Tuple

# Distribution ratio (Widmark r)
R_MALE = 0.68
R_FEMALE = 0.55

# Elimination rate (% BAC per hour)
ELIMINATION_PER_HOUR = 0.015


def _body_weight_grams(weight_lb: float) -> float:
    return weight_lb * 454.0


def bac_rise_from_grams(grams_alcohol: float, weight_lb: float, is_male: bool = True) -> float:
    """Immediate BAC rise (%) from a single dose of alcohol."""
    w_g = _body_weight_grams(weight_lb)
    r = R_MALE if is_male else R_FEMALE
    raw = grams_alcohol / (w_g * r)
    return raw * 100.0


def bac_at_time(
    time_hours: float,
    events: List[Tuple[float, float]],
    weight_lb: float,
    is_male: bool = True,
) -> float:
    """BAC (%) at a given time from a list of (time_hours, grams_alcohol) events."""
    w_g = _body_weight_grams(weight_lb)
    r = R_MALE if is_male else R_FEMALE
    bac = 0.0
    for t_drink, grams in events:
        if time_hours < t_drink:
            continue
        rise = (grams / (w_g * r)) * 100.0
        elapsed = time_hours - t_drink
        contribution = max(0.0, rise - ELIMINATION_PER_HOUR * elapsed)
        bac += contribution
    return round(bac, 4)


def _curve_end_time(
    events: List[Tuple[float, float]],
    weight_lb: float,
    is_male: bool,
    max_hours: Optional[float],
) -> float:
    """Estimated absolute end-time for plotting where BAC reaches ~0."""
    if not events:
        return 0.0

    estimated_end = max(
        t + (bac_rise_from_grams(g, weight_lb, is_male) / ELIMINATION_PER_HOUR)
        for t, g in events
    )
    if max_hours is not None:
        return min(estimated_end, max_hours)
    return estimated_end


def bac_curve(
    events: List[Tuple[float, float]],
    weight_lb: float,
    is_male: bool = True,
    step_hours: float = 0.25,
    start_hours: Optional[float] = None,
    max_hours: Optional[float] = None,
) -> List[Tuple[float, float]]:
    """Return (time_hours, bac_percent) pairs for graphing."""
    if not events:
        return []
    if step_hours <= 0:
        raise ValueError("step_hours must be > 0")

    start = 0.0 if start_hours is None else start_hours
    end = _curve_end_time(events, weight_lb, is_male, max_hours)
    end = max(end, start)

    points: List[Tuple[float, float]] = []
    t = start
    while t <= end:
        points.append((t, bac_at_time(t, events, weight_lb, is_male)))
        t += step_hours
    return points


def time_to_sober(events: List[Tuple[float, float]], weight_lb: float, is_male: bool = True) -> float:
    """Hours from first drink until BAC returns to near-zero (<= 0.001)."""
    if not events:
        return 0.0

    first = min(t for t, _ in events)
    end = first + 48.0
    t = first
    while t <= end:
        if bac_at_time(t, events, weight_lb, is_male) <= 0.001:
            return round(t - first, 2)
        t += 0.25

    return 48.0