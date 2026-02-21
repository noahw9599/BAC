"""BAC Tracker Flask app.

Run from project root:
    python app.py
"""

import os
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request, session as flask_session

from bac_app.auth_store import (
    are_friends,
    authenticate_user,
    create_user,
    find_user_by_email,
    get_user_by_id,
    get_group_role,
    get_group_snapshot,
    get_user_session_payload,
    init_db as init_auth_db,
    is_group_member,
    join_group_by_code,
    list_user_groups,
    list_friend_feed,
    list_friends,
    list_favorite_drinks,
    list_incoming_friend_requests,
    list_session_dates,
    list_user_sessions,
    respond_friend_request,
    save_user_session,
    send_friend_request,
    set_group_member_role,
    set_group_share_enabled,
    set_share_with_friends,
    track_favorite_drink,
    create_group,
    create_guardian_link,
    create_group_alert,
    get_group_snapshot_by_guardian_token,
    maybe_create_threshold_alert,
    upsert_presence,
    list_guardian_links,
    revoke_guardian_link,
    set_guardian_link_alerts,
    get_share_with_friends,
)
from bac_app.catalog import list_all_flat, list_by_category
from bac_app.drive import get_drive_advice
from bac_app.drinks import list_drink_types
from bac_app.feedback_store import init_db as init_feedback_db
from bac_app.feedback_store import list_recent, save_feedback
from bac_app.hangover import get_plan as get_hangover_plan
from bac_app.session import Session

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("APP_SECRET_KEY", "dev-only-change-me")
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

MIN_WEIGHT_LB = 80.0
MAX_WEIGHT_LB = 400.0
MIN_COUNT = 0.25
MAX_COUNT = 20.0
MAX_HOURS_AGO = 24.0
SESSION_KEY = "bac_session"
AUTH_USER_KEY = "auth_user_id"

DEFAULT_FEEDBACK_DB_PATH = str(Path("instance") / "feedback.db")
DEFAULT_AUTH_DB_PATH = str(Path("instance") / "app.db")


def _feedback_db_path() -> str:
    return os.environ.get("FEEDBACK_DB_PATH", DEFAULT_FEEDBACK_DB_PATH)


def _auth_db_path() -> str:
    return os.environ.get("APP_DB_PATH", DEFAULT_AUTH_DB_PATH)


def _ensure_feedback_db() -> None:
    db_path = Path(_feedback_db_path())
    db_path.parent.mkdir(parents=True, exist_ok=True)
    init_feedback_db(str(db_path))


def _ensure_auth_db() -> None:
    db_path = Path(_auth_db_path())
    db_path.parent.mkdir(parents=True, exist_ok=True)
    init_auth_db(str(db_path))


def _admin_token() -> str:
    return os.environ.get("ADMIN_TOKEN", "")


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
        "drive_advice": None,
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


def _require_user_id() -> int | None:
    user_id = flask_session.get(AUTH_USER_KEY)
    return user_id if isinstance(user_id, int) else None


def _get_current_user() -> dict[str, Any] | None:
    user_id = _require_user_id()
    if user_id is None:
        return None
    _ensure_auth_db()
    return get_user_by_id(_auth_db_path(), user_id)


def _auth_required_error():
    return jsonify({"error": "Authentication required"}), 401


def _is_valid_date_yyyy_mm_dd(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _social_payload(user_id: int) -> dict[str, Any]:
    _ensure_auth_db()
    return {
        "share_with_friends": get_share_with_friends(_auth_db_path(), user_id=user_id),
        "friends": list_friends(_auth_db_path(), user_id=user_id),
        "incoming_requests": list_incoming_friend_requests(_auth_db_path(), user_id=user_id),
    }


@app.route("/")
def index():
    _ensure_feedback_db()
    _ensure_auth_db()
    return render_template("index.html")


@app.route("/guardian/<token>")
def guardian_view(token: str):
    return render_template("guardian.html", token=token)


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True})


@app.route("/api/auth/me")
def api_auth_me():
    user = _get_current_user()
    if user is None:
        return jsonify({"authenticated": False, "user": None})
    return jsonify({"authenticated": True, "user": user})


@app.route("/api/auth/register", methods=["POST"])
def api_auth_register():
    _ensure_auth_db()
    data = request.get_json() or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", "")).strip()
    display_name = str(data.get("display_name", "")).strip() or email.split("@")[0]
    gender = str(data.get("gender", "")).strip().lower()
    if gender not in {"male", "female"}:
        return jsonify({"error": "Gender must be male or female"}), 400
    is_male = gender == "male"
    try:
        default_weight_lb = float(data.get("default_weight_lb"))
    except (TypeError, ValueError):
        return jsonify({"error": "Weight is required"}), 400

    if "@" not in email or len(email) < 5:
        return jsonify({"error": "Valid email is required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if len(display_name) > 40:
        return jsonify({"error": "Display name must be 40 characters or fewer"}), 400
    if default_weight_lb < MIN_WEIGHT_LB or default_weight_lb > MAX_WEIGHT_LB:
        return jsonify({"error": "Weight must be between 80 and 400 lb"}), 400

    user = create_user(
        _auth_db_path(),
        email=email,
        password=password,
        display_name=display_name,
        is_male=is_male,
        default_weight_lb=default_weight_lb,
    )
    if user is None:
        return jsonify({"error": "Email already registered"}), 409

    flask_session.permanent = True
    flask_session[AUTH_USER_KEY] = user["id"]
    return jsonify({"ok": True, "user": user})


@app.route("/api/auth/login", methods=["POST"])
def api_auth_login():
    _ensure_auth_db()
    data = request.get_json() or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", "")).strip()

    user = authenticate_user(_auth_db_path(), email=email, password=password)
    if user is None:
        return jsonify({"error": "Invalid credentials"}), 401

    flask_session.permanent = True
    flask_session[AUTH_USER_KEY] = user["id"]
    return jsonify({"ok": True, "user": user})


@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    flask_session.pop(AUTH_USER_KEY, None)
    flask_session.pop(SESSION_KEY, None)
    return jsonify({"ok": True})


@app.route("/api/social/status")
def api_social_status():
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    return jsonify(_social_payload(user_id))


@app.route("/api/social/share", methods=["POST"])
def api_social_share():
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    data = request.get_json() or {}
    enabled = bool(data.get("enabled", False))
    _ensure_auth_db()
    set_share_with_friends(_auth_db_path(), user_id=user_id, enabled=enabled)
    return jsonify({"ok": True, "share_with_friends": enabled})


@app.route("/api/social/request", methods=["POST"])
def api_social_request():
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    data = request.get_json() or {}
    email = str(data.get("email", "")).strip().lower()
    if "@" not in email:
        return jsonify({"error": "Valid email is required"}), 400
    _ensure_auth_db()
    target = find_user_by_email(_auth_db_path(), email=email)
    if target is None:
        return jsonify({"error": "User not found"}), 404
    ok, msg = send_friend_request(_auth_db_path(), from_user_id=user_id, to_user_id=target["id"])
    if not ok:
        return jsonify({"error": msg}), 400
    return jsonify({"ok": True, "message": msg})


@app.route("/api/social/request/respond", methods=["POST"])
def api_social_request_respond():
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    data = request.get_json() or {}
    try:
        request_id = int(data.get("request_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Valid request_id is required"}), 400
    action = str(data.get("action", "")).strip().lower()
    if action not in {"accept", "reject"}:
        return jsonify({"error": "Action must be accept or reject"}), 400
    _ensure_auth_db()
    ok, msg = respond_friend_request(_auth_db_path(), user_id=user_id, request_id=request_id, accept=(action == "accept"))
    if not ok:
        return jsonify({"error": msg}), 400
    return jsonify({"ok": True, "message": msg})


@app.route("/api/social/feed")
def api_social_feed():
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    _ensure_auth_db()
    items = list_friend_feed(_auth_db_path(), user_id=user_id)
    return jsonify({"items": items})


@app.route("/api/social/groups")
def api_social_groups():
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    _ensure_auth_db()
    return jsonify({"items": list_user_groups(_auth_db_path(), user_id=user_id)})


@app.route("/api/social/groups/create", methods=["POST"])
def api_social_group_create():
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    data = request.get_json() or {}
    name = str(data.get("name", "")).strip()
    if len(name) < 3:
        return jsonify({"error": "Group name must be at least 3 characters"}), 400
    _ensure_auth_db()
    group = create_group(_auth_db_path(), owner_user_id=user_id, name=name[:60])
    return jsonify({"ok": True, "group": group})


@app.route("/api/social/groups/join", methods=["POST"])
def api_social_group_join():
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    data = request.get_json() or {}
    code = str(data.get("invite_code", "")).strip().upper()
    if len(code) < 4:
        return jsonify({"error": "Invite code is required"}), 400
    _ensure_auth_db()
    ok, msg = join_group_by_code(_auth_db_path(), user_id=user_id, invite_code=code)
    if not ok:
        return jsonify({"error": msg}), 400
    return jsonify({"ok": True, "message": msg})


@app.route("/api/social/groups/<int:group_id>")
def api_social_group_snapshot(group_id: int):
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    _ensure_auth_db()
    snap = get_group_snapshot(_auth_db_path(), group_id=group_id, user_id=user_id)
    if snap is None:
        return jsonify({"error": "Group not found or access denied"}), 404
    return jsonify(snap)


@app.route("/api/social/groups/<int:group_id>/guardian-links")
def api_social_group_guardian_links(group_id: int):
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    _ensure_auth_db()
    if not is_group_member(_auth_db_path(), group_id=group_id, user_id=user_id):
        return jsonify({"error": "Not a group member"}), 403
    return jsonify({"items": list_guardian_links(_auth_db_path(), group_id=group_id)})


@app.route("/api/social/groups/<int:group_id>/guardian-links", methods=["POST"])
def api_social_group_guardian_links_create(group_id: int):
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    _ensure_auth_db()
    role = get_group_role(_auth_db_path(), group_id=group_id, user_id=user_id)
    if role not in {"owner", "mod"}:
        return jsonify({"error": "Only owner/mod can create guardian links"}), 403
    data = request.get_json() or {}
    label = str(data.get("label", "")).strip() or "Guardian"
    receive_alerts = bool(data.get("receive_alerts", True))
    link = create_guardian_link(_auth_db_path(), group_id=group_id, label=label[:40], receive_alerts=receive_alerts)
    return jsonify({"ok": True, "item": link})


@app.route("/api/social/groups/<int:group_id>/guardian-links/<int:link_id>/revoke", methods=["POST"])
def api_social_group_guardian_links_revoke(group_id: int, link_id: int):
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    _ensure_auth_db()
    role = get_group_role(_auth_db_path(), group_id=group_id, user_id=user_id)
    if role not in {"owner", "mod"}:
        return jsonify({"error": "Only owner/mod can revoke guardian links"}), 403
    ok = revoke_guardian_link(_auth_db_path(), group_id=group_id, link_id=link_id)
    if not ok:
        return jsonify({"error": "Link not found"}), 404
    return jsonify({"ok": True})


@app.route("/api/social/groups/<int:group_id>/guardian-links/<int:link_id>/alerts", methods=["POST"])
def api_social_group_guardian_links_alerts(group_id: int, link_id: int):
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    _ensure_auth_db()
    role = get_group_role(_auth_db_path(), group_id=group_id, user_id=user_id)
    if role not in {"owner", "mod"}:
        return jsonify({"error": "Only owner/mod can update guardian links"}), 403
    data = request.get_json() or {}
    enabled = bool(data.get("enabled", True))
    ok = set_guardian_link_alerts(_auth_db_path(), group_id=group_id, link_id=link_id, enabled=enabled)
    if not ok:
        return jsonify({"error": "Link not found"}), 404
    return jsonify({"ok": True, "receive_alerts": enabled})


@app.route("/api/guardian/<token>")
def api_guardian_snapshot(token: str):
    _ensure_auth_db()
    snap = get_group_snapshot_by_guardian_token(_auth_db_path(), token=token)
    if snap is None:
        return jsonify({"error": "Guardian link is invalid or revoked"}), 404
    return jsonify(snap)


@app.route("/api/social/groups/<int:group_id>/share", methods=["POST"])
def api_social_group_share(group_id: int):
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    _ensure_auth_db()
    if not is_group_member(_auth_db_path(), group_id=group_id, user_id=user_id):
        return jsonify({"error": "Not a group member"}), 403
    data = request.get_json() or {}
    enabled = bool(data.get("enabled", False))
    set_group_share_enabled(_auth_db_path(), group_id=group_id, user_id=user_id, enabled=enabled)
    return jsonify({"ok": True, "share_enabled": enabled})


@app.route("/api/social/groups/<int:group_id>/role", methods=["POST"])
def api_social_group_role(group_id: int):
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    _ensure_auth_db()
    role = get_group_role(_auth_db_path(), group_id=group_id, user_id=user_id)
    if role != "owner":
        return jsonify({"error": "Only group owner can change roles"}), 403
    data = request.get_json() or {}
    try:
        target_user_id = int(data.get("user_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Valid user_id is required"}), 400
    new_role = str(data.get("role", "")).strip().lower()
    if new_role not in {"member", "dd", "mod"}:
        return jsonify({"error": "Role must be member, dd, or mod"}), 400
    if not is_group_member(_auth_db_path(), group_id=group_id, user_id=target_user_id):
        return jsonify({"error": "Target user not in group"}), 400
    set_group_member_role(_auth_db_path(), group_id=group_id, target_user_id=target_user_id, role=new_role)
    return jsonify({"ok": True})


@app.route("/api/social/groups/<int:group_id>/location", methods=["POST"])
def api_social_group_location(group_id: int):
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    _ensure_auth_db()
    if not is_group_member(_auth_db_path(), group_id=group_id, user_id=user_id):
        return jsonify({"error": "Not a group member"}), 403
    data = request.get_json() or {}
    note = str(data.get("location_note", "")).strip()[:80]
    model = get_session()
    bac_now = round(model.bac_now(0.0), 4) if model else 0.0
    drink_count = len(model.events) if model else 0
    upsert_presence(_auth_db_path(), user_id=user_id, bac_now=bac_now, drink_count=drink_count, location_note=note)
    return jsonify({"ok": True})


@app.route("/api/social/groups/<int:group_id>/check", methods=["POST"])
def api_social_group_check(group_id: int):
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    _ensure_auth_db()
    if not is_group_member(_auth_db_path(), group_id=group_id, user_id=user_id):
        return jsonify({"error": "Not a group member"}), 403
    data = request.get_json() or {}
    try:
        target_user_id = int(data.get("target_user_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Valid target_user_id is required"}), 400
    if not is_group_member(_auth_db_path(), group_id=group_id, user_id=target_user_id):
        return jsonify({"error": "Target not in group"}), 400
    kind = str(data.get("kind", "check")).strip().lower()
    if kind not in {"check", "water", "ride"}:
        kind = "check"
    msg_map = {
        "check": "Check-in requested for a friend.",
        "water": "Water check requested for a friend.",
        "ride": "Ride-home support requested for a friend.",
    }
    create_group_alert(
        _auth_db_path(),
        group_id=group_id,
        alert_type="check",
        message=msg_map[kind],
        from_user_id=user_id,
        target_user_id=target_user_id,
    )
    return jsonify({"ok": True})


@app.route("/api/drink-types")
def api_drink_types():
    return jsonify({"drink_types": list_drink_types()})


@app.route("/api/catalog")
def api_catalog():
    by_cat = list_by_category()
    flat = list_all_flat()
    return jsonify({"by_category": by_cat, "flat": flat})


@app.route("/api/favorites")
def api_favorites():
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    _ensure_auth_db()
    return jsonify({"favorites": list_favorite_drinks(_auth_db_path(), user_id=user_id, limit=6)})


@app.route("/api/setup", methods=["POST"])
def api_setup():
    if _require_user_id() is None:
        return _auth_required_error()

    data = request.get_json() or {}
    weight = _clamp_float(data.get("weight_lb"), 160.0, MIN_WEIGHT_LB, MAX_WEIGHT_LB)
    is_male = _parse_bool(data.get("is_male"), default=True)
    set_session(Session(weight_lb=weight, is_male=is_male))
    return jsonify({"ok": True, "weight_lb": weight, "is_male": is_male})


@app.route("/api/drink", methods=["POST"])
def api_drink():
    if _require_user_id() is None:
        return _auth_required_error()

    model = get_session()
    if model is None:
        return jsonify({"error": "Set weight and sex first"}), 400

    data = request.get_json() or {}
    count = _clamp_float(data.get("count"), 1.0, MIN_COUNT, MAX_COUNT)
    hours_ago = _clamp_float(data.get("hours_ago"), 0.0, 0.0, MAX_HOURS_AGO)

    if data.get("catalog_id"):
        catalog_id = data["catalog_id"]
        model.add_drink_catalog(hours_ago, catalog_id, count)
        _ensure_auth_db()
        track_favorite_drink(_auth_db_path(), user_id=_require_user_id(), catalog_id=catalog_id)
    else:
        drink_key = data.get("drink_key", "beer")
        model.add_drink_ago(hours_ago, drink_key, count)

    set_session(model)
    return jsonify({"ok": True})


@app.route("/api/state")
def api_state():
    user_id = _require_user_id()
    if user_id is None:
        return jsonify({"authenticated": False, **_empty_state()})

    model = get_session()
    hours_until_target = request.args.get("hours_until_target", type=float)

    if model is None:
        _ensure_auth_db()
        upsert_presence(_auth_db_path(), user_id=user_id, bac_now=0.0, drink_count=0)
        return jsonify({"authenticated": True, **_empty_state()})

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

    bac_now = round(model.bac_now(0.0), 4)
    _ensure_auth_db()
    upsert_presence(_auth_db_path(), user_id=user_id, bac_now=bac_now, drink_count=len(events))
    maybe_create_threshold_alert(_auth_db_path(), user_id=user_id, bac_now=bac_now)

    return jsonify({
        "authenticated": True,
        "configured": True,
        "weight_lb": model.weight_lb,
        "is_male": model.is_male,
        "bac_now": bac_now,
        "curve": [{"t": t, "bac": bac} for t, bac in curve],
        "hours_until_sober_from_now": model.hours_until_sober_from_now(),
        "drink_count": len(events),
        "total_calories": model.total_calories,
        "total_carbs_g": round(model.total_carbs_g, 1),
        "total_sugar_g": round(model.total_sugar_g, 1),
        "hangover_plan": hangover_plan,
        "drive_advice": get_drive_advice(bac_now, model.hours_until_sober_from_now()),
    })


@app.route("/api/hangover-plan")
def api_hangover_plan():
    if _require_user_id() is None:
        return _auth_required_error()

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
    if _require_user_id() is None:
        return _auth_required_error()

    model = get_session()
    if model is None:
        return jsonify({"ok": True})
    set_session(Session(weight_lb=model.weight_lb, is_male=model.is_male))
    return jsonify({"ok": True})


@app.route("/api/session/save", methods=["POST"])
def api_session_save():
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()

    _ensure_auth_db()
    model = get_session()
    if model is None:
        return jsonify({"error": "No active session to save"}), 400

    data = request.get_json() or {}
    name = str(data.get("name", "")).strip() or "Untitled session"
    if len(name) > 80:
        return jsonify({"error": "Name must be 80 characters or fewer"}), 400

    session_id = save_user_session(
        _auth_db_path(),
        user_id=user_id,
        name=name,
        payload=_session_to_cookie(model),
    )
    return jsonify({"ok": True, "session_id": session_id})


@app.route("/api/session/list")
def api_session_list():
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()

    _ensure_auth_db()
    session_date = request.args.get("date", type=str)
    if session_date and not _is_valid_date_yyyy_mm_dd(session_date):
        return jsonify({"error": "date must be YYYY-MM-DD"}), 400

    items = list_user_sessions(_auth_db_path(), user_id=user_id, session_date=session_date)
    return jsonify({"items": items})


@app.route("/api/session/dates")
def api_session_dates():
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    _ensure_auth_db()
    return jsonify({"items": list_session_dates(_auth_db_path(), user_id=user_id)})


@app.route("/api/session/load", methods=["POST"])
def api_session_load():
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()

    _ensure_auth_db()
    data = request.get_json() or {}
    try:
        session_id = int(data.get("session_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Valid session_id is required"}), 400

    payload = get_user_session_payload(_auth_db_path(), user_id=user_id, session_id=session_id)
    if payload is None:
        return jsonify({"error": "Saved session not found"}), 404

    model = _session_from_cookie(payload)
    if model is None:
        return jsonify({"error": "Saved session is invalid"}), 400

    set_session(model)
    return jsonify({"ok": True})


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    _ensure_feedback_db()
    data = request.get_json() or {}
    message = str(data.get("message", "")).strip()
    if not message:
        return jsonify({"error": "message is required"}), 400
    message = message[:1200]

    rating_raw = data.get("rating")
    rating = None
    if rating_raw is not None and rating_raw != "":
        try:
            rating = int(rating_raw)
        except (TypeError, ValueError):
            return jsonify({"error": "rating must be an integer 1-5"}), 400
        if rating < 1 or rating > 5:
            return jsonify({"error": "rating must be between 1 and 5"}), 400

    contact = str(data.get("contact", "")).strip()[:120] or None
    context = data.get("context")
    if not isinstance(context, dict):
        context = {}

    feedback_id = save_feedback(
        _feedback_db_path(),
        message=message,
        rating=rating,
        contact=contact,
        context=context,
        user_agent=request.headers.get("User-Agent", ""),
    )
    return jsonify({"ok": True, "feedback_id": feedback_id})


@app.route("/api/feedback/recent")
def api_feedback_recent():
    _ensure_feedback_db()
    token = request.args.get("token", "")
    if not _admin_token() or token != _admin_token():
        return jsonify({"error": "forbidden"}), 403

    limit = request.args.get("limit", type=int) or 25
    return jsonify({"items": list_recent(_feedback_db_path(), limit=limit)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
