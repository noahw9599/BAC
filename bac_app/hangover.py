"""Pace-aware hangover planning helpers.

Given logged drinks and a target time (for example, class or work),
this module estimates rough risk bands and a dynamic stop-by guidance.
"""

from typing import List, Optional, Tuple

from bac_app import calculations

# Recommend last drink at least this many hours before target.
HOURS_BEFORE_TARGET_TO_STOP = 10
SOBER_BAC_THRESHOLD = 0.001
PACE_LOOKBACK_HOURS = 3.0
PROJECTION_STEP_HOURS = 0.5

LOW_RISK_PEAK_BAC = 0.05
HIGH_RISK_PEAK_BAC = 0.10


def _peak_bac(events: List[Tuple[float, float]], weight_lb: float, is_male: bool) -> float:
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


def _estimate_recent_rate_grams_per_hour(events: List[Tuple[float, float]]) -> float:
    """Estimate current drinking pace from recent events, in grams/hour."""
    if not events:
        return 0.0
    window_start = -PACE_LOOKBACK_HOURS
    recent = [(t, g) for t, g in events if t >= window_start]
    if not recent:
        return 0.0
    grams = sum(max(0.0, g) for _, g in recent)
    earliest = min(t for t, _ in recent)
    span_hours = max(1.0, -earliest)
    return grams / span_hours


def _projected_events(events: List[Tuple[float, float]], grams_per_hour: float, stop_by_hours_from_now: float) -> List[Tuple[float, float]]:
    if grams_per_hour <= 0 or stop_by_hours_from_now <= 0:
        return list(events)
    projected = list(events)
    t = 0.0
    while t < stop_by_hours_from_now:
        dt = min(PROJECTION_STEP_HOURS, stop_by_hours_from_now - t)
        projected.append((t, grams_per_hour * dt))
        t += PROJECTION_STEP_HOURS
    return projected


def _pace_based_stop_by(
    events: List[Tuple[float, float]],
    weight_lb: float,
    is_male: bool,
    hours_until_target: float,
) -> tuple[float, float]:
    """Return (stop_by_hours_from_now, estimated_drinks_per_hour)."""
    grams_per_hour = _estimate_recent_rate_grams_per_hour(events)
    drinks_per_hour = grams_per_hour / 14.0 if grams_per_hour > 0 else 0.0

    # Baseline: stop now.
    bac_if_stop_now = calculations.bac_at_time(hours_until_target, events, weight_lb, is_male)
    if bac_if_stop_now > SOBER_BAC_THRESHOLD:
        # Already unlikely to be sober by target; negative means should have stopped earlier.
        extra_hours = (bac_if_stop_now - SOBER_BAC_THRESHOLD) / calculations.ELIMINATION_PER_HOUR
        return -round(max(0.0, extra_hours), 2), drinks_per_hour

    if grams_per_hour <= 0:
        return 0.0, 0.0

    lo = 0.0
    hi = max(0.0, hours_until_target)
    # Binary search latest time you can keep drinking at current pace and still be sober by target.
    for _ in range(24):
        mid = (lo + hi) / 2.0
        projected = _projected_events(events, grams_per_hour, mid)
        bac_at_target = calculations.bac_at_time(hours_until_target, projected, weight_lb, is_male)
        if bac_at_target <= SOBER_BAC_THRESHOLD:
            lo = mid
        else:
            hi = mid
    return round(lo, 2), drinks_per_hour


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
    pace_stop_by, drinks_per_hour = _pace_based_stop_by(events, weight_lb, is_male, hours_until_target)
    fixed_stop_by = recommend_stop_by_hours(hours_until_target)
    # Use pace-aware value when there is pace data; otherwise fall back to fixed guidance.
    stop_by = pace_stop_by if events else fixed_stop_by

    if risk == "low":
        message = "You are on track. Stay hydrated and get sleep."
    elif risk == "medium":
        message = "You may feel off tomorrow. Consider stopping soon and drinking water."
    else:
        message = "High chance of a rough morning. Stop now, hydrate, and rest."
    if drinks_per_hour > 0:
        message = f"{message} Current pace estimate: {drinks_per_hour:.1f} drinks/hour."

    return {
        "stop_by_hours_from_now": round(stop_by, 1),
        "fixed_stop_by_hours_from_now": round(fixed_stop_by, 1),
        "hours_until_target": hours_until_target,
        "hangover_risk": risk,
        "peak_bac": round(peak, 4),
        "estimated_drinks_per_hour": round(drinks_per_hour, 2),
        "message": message,
    }
