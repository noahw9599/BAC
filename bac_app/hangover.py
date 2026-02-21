"""Simple hangover planning helpers.

Given logged drinks and a target time (for example, class or work),
this module estimates rough risk bands and stop-by guidance.
"""

from typing import List, Optional, Tuple

# Recommend last drink at least this many hours before target.
HOURS_BEFORE_TARGET_TO_STOP = 10

LOW_RISK_PEAK_BAC = 0.05
HIGH_RISK_PEAK_BAC = 0.10


def _peak_bac(events: List[Tuple[float, float]], weight_lb: float, is_male: bool) -> float:
    from bac_app import calculations

    if not events:
        return 0.0

    peak = 0.0
    t = min(t for t, _ in events)
    end = t + 24.0
    step = 0.25
    while t <= end:
        bac = calculations.bac_at_time(t, events, weight_lb, is_male)
        peak = max(peak, bac)
        t += step
    return peak


def _last_drink_time(events: List[Tuple[float, float]]) -> Optional[float]:
    if not events:
        return None
    return max(t for t, _ in events)


def hangover_risk(peak_bac: float, hours_from_last_drink_to_target: float) -> str:
    """Return risk band: 'low', 'medium', or 'high'."""
    if hours_from_last_drink_to_target >= HOURS_BEFORE_TARGET_TO_STOP and peak_bac < 0.08:
        return "low"
    if hours_from_last_drink_to_target >= 6 and peak_bac < HIGH_RISK_PEAK_BAC:
        return "medium"
    if peak_bac >= HIGH_RISK_PEAK_BAC or hours_from_last_drink_to_target < 6:
        return "high"
    return "medium"


def recommend_stop_by_hours(hours_until_target: float) -> float:
    """Hours from now when the last drink should occur (can be negative)."""
    return hours_until_target - HOURS_BEFORE_TARGET_TO_STOP


def get_plan(
    events: List[Tuple[float, float]],
    weight_lb: float,
    is_male: bool,
    hours_until_target: float,
) -> dict:
    """Return stop-by estimate and hangover-risk guidance."""
    peak = _peak_bac(events, weight_lb, is_male)
    last_t = _last_drink_time(events)

    if last_t is None:
        hours_from_last_to_target = hours_until_target + 999
    else:
        hours_from_last_to_target = -last_t + hours_until_target

    risk = hangover_risk(peak, hours_from_last_to_target)
    stop_by = recommend_stop_by_hours(hours_until_target)

    if risk == "low":
        message = "You are on track. Stay hydrated and get sleep."
    elif risk == "medium":
        message = "You may feel off tomorrow. Consider stopping soon and drinking water."
    else:
        message = "High chance of a rough morning. Stop now, hydrate, and rest."

    return {
        "stop_by_hours_from_now": round(stop_by, 1),
        "hours_until_target": hours_until_target,
        "hangover_risk": risk,
        "peak_bac": round(peak, 4),
        "message": message,
    }