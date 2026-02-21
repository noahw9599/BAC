"""
BAC calculations using Widmark-style formula and linear elimination.
- Rise: BAC = [grams / (body_weight_g × r)] × 100
- r = 0.68 male, 0.55 female
- Elimination: 0.015% BAC per hour (typical)
"""

from typing import List, Optional, Tuple

# Distribution ratio (Widmark r): male 0.68, female 0.55
R_MALE = 0.68
R_FEMALE = 0.55

# Elimination rate (% BAC per hour)
ELIMINATION_PER_HOUR = 0.015


def _body_weight_grams(weight_lb: float) -> float:
    return weight_lb * 454.0


def bac_rise_from_grams(grams_alcohol: float, weight_lb: float, is_male: bool = True) -> float:
    """
    Immediate BAC rise (%) from a single dose of alcohol (Widmark).
    weight_lb: body weight in pounds.
    """
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
    """
    BAC (%) at a given time from a list of (time_hours, grams_alcohol) events.
    Each drink adds a rise then decays at ELIMINATION_PER_HOUR.
    """
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


def bac_curve(
    events: List[Tuple[float, float]],
    weight_lb: float,
    is_male: bool = True,
    step_hours: float = 0.25,
    start_hours: Optional[float] = None,
    max_hours: Optional[float] = None,
) -> List[Tuple[float, float]]:
    """
    (time_hours, bac_percent) pairs for graphing.
    start_hours: first time (default: 0). Use negative to show past (e.g. "now" = 0, drinks in past).
    If max_hours is None, run until BAC would be 0 (based on last event).
    """
    if not events:
        return []
    if start_hours is None:
        start_hours = 0.0
    last_time = max(t for t, _ in events)
    last_grams = sum(g for t, g in events if t == last_time)
    rise_last = bac_rise_from_grams(last_grams, weight_lb, is_male)
    duration = last_time + (rise_last / ELIMINATION_PER_HOUR) if ELIMINATION_PER_HOUR else 24.0
    if max_hours is not None:
        duration = min(duration, max_hours)
    duration = max(duration, start_hours)
    points = []
    t = start_hours
    while t <= duration:
        bac = bac_at_time(t, events, weight_lb, is_male)
        points.append((t, bac))
        t += step_hours
    return points


def time_to_sober(events: List[Tuple[float, float]], weight_lb: float, is_male: bool = True) -> float:
    """Hours from first drink until BAC returns to 0 (within 0.001%)."""
    if not events:
        return 0.0
    first = min(t for t, _ in events)
    # sample from first drink to 48h
    curve = bac_curve(events, weight_lb, is_male, step_hours=0.25, max_hours=48.0)
    for t, bac in reversed(curve):
        if bac <= 0.001:
            return t - first
    return 48.0 - first
