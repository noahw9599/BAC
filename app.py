"""BAC Tracker Flask app.

Run from project root:
    python app.py
"""

import os
from typing import Any

from flask import Flask, jsonify, render_template, request

from bac_app.catalog import list_all_flat, list_by_category
from bac_app.drinks import list_drink_types
from bac_app.hangover import get_plan as get_hangover_plan
from bac_app.session import Session

app = Flask(__name__)

MIN_WEIGHT_LB = 80.0
MAX_WEIGHT_LB = 400.0
MIN_COUNT = 0.25
MAX_COUNT = 20.0
MAX_HOURS_AGO = 24.0

_current_session: Session | None = None


def get_session() -> Session | None:
    return _current_session


def set_session(session: Session | None):
    global _current_session
    _current_session = session


def _parse_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y", "male"}:
            return True
        if lowered in {"false", "0", "no", "n", "female"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _clamp_float(value: Any, default: float, min_value: float, max_value: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(min_value, min(max_value, parsed))


def _empty_state() -> dict[str, Any]:
    return {
        "configured": False,
        "bac_now": 0,
        "curve": [],
        "hours_until_sober_from_now": 0,
        "drink_count": 0,
        "total_calories": 0,
        "total_carbs_g": 0,
        "total_sugar_g": 0,
        "hangover_plan": None,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True})


@app.route("/api/drink-types")
def api_drink_types():
    return jsonify({"drink_types": list_drink_types()})


@app.route("/api/catalog")
def api_catalog():
    """Catalog by category (for grouped UI) and flat list (for single dropdown)."""
    by_cat = list_by_category()
    flat = list_all_flat()
    return jsonify({"by_category": by_cat, "flat": flat})


@app.route("/api/setup", methods=["POST"])
def api_setup():
    data = request.get_json() or {}
    weight = _clamp_float(data.get("weight_lb"), 160.0, MIN_WEIGHT_LB, MAX_WEIGHT_LB)
    is_male = _parse_bool(data.get("is_male"), default=True)
    set_session(Session(weight_lb=weight, is_male=is_male))
    return jsonify({"ok": True, "weight_lb": weight, "is_male": is_male})


@app.route("/api/drink", methods=["POST"])
def api_drink():
    session = get_session()
    if session is None:
        return jsonify({"error": "Set weight and sex first"}), 400

    data = request.get_json() or {}
    count = _clamp_float(data.get("count"), 1.0, MIN_COUNT, MAX_COUNT)
    hours_ago = _clamp_float(data.get("hours_ago"), 0.0, 0.0, MAX_HOURS_AGO)

    if data.get("catalog_id"):
        session.add_drink_catalog(hours_ago, data["catalog_id"], count)
    else:
        drink_key = data.get("drink_key", "beer")
        session.add_drink_ago(hours_ago, drink_key, count)
    return jsonify({"ok": True})


@app.route("/api/state")
def api_state():
    session = get_session()
    hours_until_target = request.args.get("hours_until_target", type=float)

    if session is None:
        return jsonify(_empty_state())

    events = session.events
    start_h = min((t for t, _ in events), default=0) - 0.5
    start_h = min(start_h, -0.25)
    end_h = session.hours_until_sober_from_now() + 1.0
    curve = session.curve(step_hours=0.25, start_hours=start_h, max_hours=max(end_h, 2))

    hangover_plan = None
    if hours_until_target is not None and hours_until_target >= 0:
        hangover_plan = get_hangover_plan(
            session.events_bac,
            session.weight_lb,
            session.is_male,
            hours_until_target,
        )

    return jsonify({
        "configured": True,
        "weight_lb": session.weight_lb,
        "is_male": session.is_male,
        "bac_now": round(session.bac_now(0.0), 4),
        "curve": [{"t": t, "bac": bac} for t, bac in curve],
        "hours_until_sober_from_now": session.hours_until_sober_from_now(),
        "drink_count": len(events),
        "total_calories": session.total_calories,
        "total_carbs_g": round(session.total_carbs_g, 1),
        "total_sugar_g": round(session.total_sugar_g, 1),
        "hangover_plan": hangover_plan,
    })


@app.route("/api/hangover-plan")
def api_hangover_plan():
    session = get_session()
    hours = request.args.get("hours_until_target", type=float)
    if session is None or hours is None or hours < 0:
        return jsonify({"error": "Configure session and provide hours_until_target"}), 400

    plan = get_hangover_plan(
        session.events_bac,
        session.weight_lb,
        session.is_male,
        hours,
    )
    return jsonify(plan)


@app.route("/api/reset", methods=["POST"])
def api_reset():
    session = get_session()
    if session is None:
        return jsonify({"ok": True})
    set_session(Session(weight_lb=session.weight_lb, is_male=session.is_male))
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")