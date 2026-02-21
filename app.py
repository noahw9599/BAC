"""BAC Tracker Flask app.

Run from project root:
    python app.py
"""

import os
from typing import Any

from flask import Flask, jsonify, render_template, request, session as flask_session

from bac_app.catalog import list_all_flat, list_by_category
from bac_app.drinks import list_drink_types
from bac_app.hangover import get_plan as get_hangover_plan
from bac_app.session import Session

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("APP_SECRET_KEY", "dev-only-change-me")
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"

MIN_WEIGHT_LB = 80.0
MAX_WEIGHT_LB = 400.0
MIN_COUNT = 0.25
MAX_COUNT = 20.0
MAX_HOURS_AGO = 24.0
SESSION_KEY = "bac_session"


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


def _session_to_cookie(model: Session) -> dict[str, Any]:
    return {
        "weight_lb": model.weight_lb,
        "is_male": model.is_male,
        "events": [list(e) for e in model.events_full],
    }


def _session_from_cookie(raw: Any) -> Session | None:
    if not isinstance(raw, dict):
        return None

    weight = _clamp_float(raw.get("weight_lb"), 160.0, MIN_WEIGHT_LB, MAX_WEIGHT_LB)
    is_male = _parse_bool(raw.get("is_male"), default=True)
    events_raw = raw.get("events", [])

    model = Session(weight_lb=weight, is_male=is_male)
    if isinstance(events_raw, list):
        for event in events_raw:
            if not isinstance(event, (list, tuple)) or len(event) != 5:
                continue
            t = _clamp_float(event[0], 0.0, -MAX_HOURS_AGO, 0.0)
            grams = _clamp_float(event[1], 0.0, 0.0, 1000.0)
            calories = int(_clamp_float(event[2], 0.0, 0.0, 5000.0))
            carbs = _clamp_float(event[3], 0.0, 0.0, 1000.0)
            sugar = _clamp_float(event[4], 0.0, 0.0, 1000.0)
            model.add_drink_grams(t, grams, calories=calories, carbs_g=carbs, sugar_g=sugar)
    return model


def get_session() -> Session | None:
    return _session_from_cookie(flask_session.get(SESSION_KEY))


def set_session(model: Session | None):
    if model is None:
        flask_session.pop(SESSION_KEY, None)
        return
    flask_session[SESSION_KEY] = _session_to_cookie(model)


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
    model = get_session()
    if model is None:
        return jsonify({"error": "Set weight and sex first"}), 400

    data = request.get_json() or {}
    count = _clamp_float(data.get("count"), 1.0, MIN_COUNT, MAX_COUNT)
    hours_ago = _clamp_float(data.get("hours_ago"), 0.0, 0.0, MAX_HOURS_AGO)

    if data.get("catalog_id"):
        model.add_drink_catalog(hours_ago, data["catalog_id"], count)
    else:
        drink_key = data.get("drink_key", "beer")
        model.add_drink_ago(hours_ago, drink_key, count)

    set_session(model)
    return jsonify({"ok": True})


@app.route("/api/state")
def api_state():
    model = get_session()
    hours_until_target = request.args.get("hours_until_target", type=float)

    if model is None:
        return jsonify(_empty_state())

    events = model.events
    start_h = min((t for t, _ in events), default=0) - 0.5
    start_h = min(start_h, -0.25)
    end_h = model.hours_until_sober_from_now() + 1.0
    curve = model.curve(step_hours=0.25, start_hours=start_h, max_hours=max(end_h, 2))

    hangover_plan = None
    if hours_until_target is not None and hours_until_target >= 0:
        hangover_plan = get_hangover_plan(
            model.events_bac,
            model.weight_lb,
            model.is_male,
            hours_until_target,
        )

    return jsonify({
        "configured": True,
        "weight_lb": model.weight_lb,
        "is_male": model.is_male,
        "bac_now": round(model.bac_now(0.0), 4),
        "curve": [{"t": t, "bac": bac} for t, bac in curve],
        "hours_until_sober_from_now": model.hours_until_sober_from_now(),
        "drink_count": len(events),
        "total_calories": model.total_calories,
        "total_carbs_g": round(model.total_carbs_g, 1),
        "total_sugar_g": round(model.total_sugar_g, 1),
        "hangover_plan": hangover_plan,
    })


@app.route("/api/hangover-plan")
def api_hangover_plan():
    model = get_session()
    hours = request.args.get("hours_until_target", type=float)
    if model is None or hours is None or hours < 0:
        return jsonify({"error": "Configure session and provide hours_until_target"}), 400

    plan = get_hangover_plan(
        model.events_bac,
        model.weight_lb,
        model.is_male,
        hours,
    )
    return jsonify(plan)


@app.route("/api/reset", methods=["POST"])
def api_reset():
    model = get_session()
    if model is None:
        return jsonify({"ok": True})
    set_session(Session(weight_lb=model.weight_lb, is_male=model.is_male))
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")