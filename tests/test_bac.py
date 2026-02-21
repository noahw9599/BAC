"""Basic tests for BAC calculations and session. Run from project root: pytest tests/ -v"""
from bac_app.calculations import bac_at_time, bac_rise_from_grams
from bac_app.session import Session
from bac_app.drinks import grams_from_drink, STANDARD_DRINK_GRAMS


def test_standard_drink_grams():
    assert grams_from_drink("beer", count=1) == STANDARD_DRINK_GRAMS
    assert grams_from_drink("beer", count=2) == STANDARD_DRINK_GRAMS * 2


def test_bac_rise():
    # 160 lb male, 1 standard drink -> small rise
    rise = bac_rise_from_grams(14, 160, is_male=True)
    assert 0.01 < rise < 0.05


def test_bac_at_time():
    events = [(0, 14), (1, 14)]  # 2 drinks at t=0 and t=1
    bac0 = bac_at_time(0, events, 160, True)
    bac1 = bac_at_time(1, events, 160, True)
    bac2 = bac_at_time(2, events, 160, True)
    assert bac1 > bac0
    assert bac2 < bac1  # elimination


def test_session_add_drink_ago():
    s = Session(weight_lb=160, is_male=True)
    s.add_drink_ago(0, "beer", 1)
    s.add_drink_ago(0.5, "beer", 1)
    assert len(s.events) == 2
    assert s.bac_now(0) > 0
    assert s.hours_until_sober_from_now() >= 0


def test_curve_with_past():
    s = Session(weight_lb=160, is_male=True)
    s.add_drink_ago(1, "beer", 1)
    curve = s.curve(start_hours=-0.5, max_hours=3)
    assert len(curve) > 0
    ts = [p[0] for p in curve]
    assert any(t <= 0.01 and t >= -0.01 for t in ts)


def test_session_catalog_nutrition():
    s = Session(weight_lb=160, is_male=True)
    s.add_drink_catalog(0, "bud-light", 2)
    # add_drink_catalog(hours_ago, catalog_id, count) stores one aggregated event for count
    assert len(s.events) == 1
    assert s.total_calories == 110 * 2
    assert s.total_carbs_g == 6.6 * 2


def test_hangover_plan():
    from bac_app.hangover import get_plan
    events = [(-1, 28), (0, 14)]  # drinks 1h ago and now
    plan = get_plan(events, 160, True, 10)
    assert "hangover_risk" in plan
    assert plan["hangover_risk"] in ("low", "medium", "high")
    assert "stop_by_hours_from_now" in plan
    assert "message" in plan
