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

from bac_app import calculations
from bac_app.auth_store import (
    add_friendship,
    are_friends,
    authenticate_user,
    create_user,
    find_user_by_email,
    find_user_by_invite_code,
    find_user_by_username,
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
    list_recent_session_payloads,
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
    get_active_auto_session,
    upsert_auto_session,
    finalize_active_auto_session,
    upsert_presence,
    list_guardian_links,
    revoke_guardian_link,
    set_guardian_link_alerts,
    get_share_with_friends,
    revoke_all_sharing_for_user,
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
TRACKING_META_KEY = "tracking_meta"
INACTIVITY_EXPIRE_HOURS = 3.0
MAX_ACTIVE_SESSION_HOURS = 12.0
AUTOSAVE_INTERVAL_MINUTES = 5.0

DEFAULT_FEEDBACK_DB_PATH = str(Path("instance") / "feedback.db")
DEFAULT_AUTH_DB_PATH = str(Path("instance") / "app.db")

CAMPUS_PRESETS = [
    {
        "id": "generic",
        "name": "Generic Campus",
        "safe_ride_label": "Campus Safe Ride",
        "safe_ride_url": "",
        "non_emergency_phone": "",
        "emergency_phone": "911",
    },
    {
        "id": "asu",
        "name": "Arizona State University",
        "safe_ride_label": "ASU Safety Escort",
        "safe_ride_url": "https://cfo.asu.edu/safety-escort",
        "non_emergency_phone": "480-965-3456",
        "emergency_phone": "911",
    },
    {
        "id": "ucla",
        "name": "UCLA",
        "safe_ride_label": "CSO Safety Escort",
        "safe_ride_url": "https://police.ucla.edu/how-we-can-help/security-escort",
        "non_emergency_phone": "310-825-1491",
        "emergency_phone": "911",
    },
]


def _feedback_db_path() -> str:
    return os.environ.get("FEEDBACK_DB_PATH", DEFAULT_FEEDBACK_DB_PATH)


def _auth_db_path() -> str:
    return os.environ.get("APP_DB_PATH") or os.environ.get("DATABASE_URL", DEFAULT_AUTH_DB_PATH)


def _is_db_url(value: str) -> bool:
    return value.startswith("postgres://") or value.startswith("postgresql://")


def _ensure_feedback_db() -> None:
    db_path = Path(_feedback_db_path())
    db_path.parent.mkdir(parents=True, exist_ok=True)
    init_feedback_db(str(db_path))


def _ensure_auth_db() -> None:
    db_path = _auth_db_path()
    if not _is_db_url(db_path):
        path_obj = Path(db_path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
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
        "session_events": [],
        "drink_count": 0,
        "total_calories": 0,
        "total_carbs_g": 0,
        "total_sugar_g": 0,
        "hangover_plan": None,
        "drive_advice": None,
        "pace_prediction": None,
        "chart_data": None,
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


def _session_events_payload(model: Session) -> list[dict[str, Any]]:
    events = model.events_full
    out: list[dict[str, Any]] = []
    for idx, e in enumerate(events):
        t, grams, calories, carbs, sugar = e
        out.append(
            {
                "index": idx,
                "hours_ago": round(abs(float(t)), 2),
                "standard_drinks": round(float(grams) / 14.0, 2),
                "grams_alcohol": round(float(grams), 2),
                "calories": int(calories),
                "carbs_g": round(float(carbs), 2),
                "sugar_g": round(float(sugar), 2),
            }
        )
    return out


def _rebuild_model_from_events(base: Session, events: list[tuple[float, float, int, float, float]]) -> Session:
    model = Session(weight_lb=base.weight_lb, is_male=base.is_male)
    for t, grams, calories, carbs, sugar in events:
        model.add_drink_grams(float(t), float(grams), calories=int(calories), carbs_g=float(carbs), sugar_g=float(sugar))
    return model


def _estimate_rate_grams_per_hour(events_bac: list[tuple[float, float]], lookback_hours: float = 3.0) -> float:
    if not events_bac:
        return 0.0
    recent = [(t, g) for t, g in events_bac if t >= -lookback_hours]
    if not recent:
        return 0.0
    grams = sum(max(0.0, g) for _, g in recent)
    earliest = min(t for t, _ in recent)
    span = max(1.0, -earliest)
    return grams / span


def _project_curve_with_rate(
    events_bac: list[tuple[float, float]],
    *,
    grams_per_hour: float,
    weight_lb: float,
    is_male: bool,
    horizon_hours: float,
) -> list[dict[str, float]]:
    projected = list(events_bac)
    if grams_per_hour > 0 and horizon_hours > 0:
        t = 0.0
        while t < horizon_hours:
            dt = min(0.5, horizon_hours - t)
            projected.append((t, grams_per_hour * dt))
            t += 0.5
    curve = calculations.bac_curve(projected, weight_lb, is_male, step_hours=0.25, start_hours=-6.0, max_hours=24.0)
    return [{"t": t, "bac": bac} for t, bac in curve]


def _single_drink_projection(
    events_bac: list[tuple[float, float]],
    *,
    at_hours: float,
    weight_lb: float,
    is_male: bool,
) -> list[dict[str, float]]:
    projected = list(events_bac) + [(at_hours, 14.0)]
    curve = calculations.bac_curve(projected, weight_lb, is_male, step_hours=0.25, start_hours=-6.0, max_hours=24.0)
    return [{"t": t, "bac": bac} for t, bac in curve]


def _confidence_band(curve: list[tuple[float, float]], delta: float = 0.01) -> dict[str, list[dict[str, float]]]:
    lower = [{"t": t, "bac": max(0.0, bac - delta)} for t, bac in curve]
    upper = [{"t": t, "bac": max(0.0, bac + delta)} for t, bac in curve]
    return {"lower": lower, "upper": upper}


def _event_markers(events_bac: list[tuple[float, float]], *, weight_lb: float, is_male: bool) -> list[dict[str, float]]:
    out: list[dict[str, float]] = []
    for t, _ in events_bac:
        out.append({"t": t, "bac": calculations.bac_at_time(t, events_bac, weight_lb, is_male)})
    return out


def _compare_curve_from_history(user_id: int, model: Session, base_curve: list[tuple[float, float]]) -> list[dict[str, float]]:
    _ensure_auth_db()
    payloads = list_recent_session_payloads(_auth_db_path(), user_id=user_id, limit=5)
    if not payloads:
        return []
    sessions: list[Session] = []
    for payload in payloads:
        m = _session_from_cookie(payload)
        if m is not None and m.events_bac:
            sessions.append(m)
    if not sessions:
        return []
    points: list[dict[str, float]] = []
    for t, _ in base_curve:
        vals = [calculations.bac_at_time(t, s.events_bac, s.weight_lb, s.is_male) for s in sessions]
        if vals:
            points.append({"t": t, "bac": round(sum(vals) / len(vals), 4)})
    return points


def get_session() -> Session | None:
    return _session_from_cookie(flask_session.get(SESSION_KEY))


def set_session(model: Session | None):
    if model is None:
        flask_session.pop(SESSION_KEY, None)
        return
    flask_session[SESSION_KEY] = _session_to_cookie(model)


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _hours_since(iso_value: str | None) -> float | None:
    dt = _parse_iso(iso_value)
    if dt is None:
        return None
    return (datetime.now() - dt).total_seconds() / 3600.0


def _minutes_since(iso_value: str | None) -> float | None:
    dt = _parse_iso(iso_value)
    if dt is None:
        return None
    return (datetime.now() - dt).total_seconds() / 60.0


def _get_tracking_meta() -> dict[str, Any]:
    raw = flask_session.get(TRACKING_META_KEY)
    return raw if isinstance(raw, dict) else {}


def _set_tracking_meta(meta: dict[str, Any] | None) -> None:
    if not meta:
        flask_session.pop(TRACKING_META_KEY, None)
        return
    flask_session[TRACKING_META_KEY] = meta


def _default_auto_session_name(now_dt: datetime | None = None) -> str:
    dt = now_dt or datetime.now()
    return dt.strftime("%a %b %d - %I:%M %p")


def _touch_tracking_meta(*, on_drink: bool = False, reset: bool = False) -> dict[str, Any]:
    if reset:
        _set_tracking_meta(None)
        return {}
    now = _now_iso()
    meta = _get_tracking_meta()
    if not meta.get("session_started_at"):
        meta["session_started_at"] = now
    if on_drink:
        meta["last_drink_at"] = now
    meta["last_autosave_at"] = now
    _set_tracking_meta(meta)
    return meta


def _record_auto_session(user_id: int, model: Session, *, touch_last_event: bool) -> None:
    _ensure_auth_db()
    meta = _get_tracking_meta()
    event_time_iso = _now_iso()
    if touch_last_event:
        meta["last_drink_at"] = event_time_iso
    if not meta.get("session_started_at"):
        meta["session_started_at"] = event_time_iso
    meta["last_autosave_at"] = event_time_iso
    _set_tracking_meta(meta)
    upsert_auto_session(
        _auth_db_path(),
        user_id=user_id,
        name=_default_auto_session_name(),
        payload=_session_to_cookie(model),
        event_time_iso=event_time_iso,
        touch_last_event=touch_last_event,
    )


def _finalize_auto_session_and_reset(user_id: int, model: Session | None) -> None:
    _ensure_auth_db()
    finalize_active_auto_session(_auth_db_path(), user_id=user_id, ended_at_iso=_now_iso())
    if model is not None:
        set_session(Session(weight_lb=model.weight_lb, is_male=model.is_male))
    _set_tracking_meta(None)


def _expire_current_session_if_needed(user_id: int, model: Session | None) -> bool:
    if model is None or not model.events:
        return False
    meta = _get_tracking_meta()
    _ensure_auth_db()
    active = get_active_auto_session(_auth_db_path(), user_id=user_id)
    started_iso = meta.get("session_started_at") or (active["started_at"] if active else None)
    last_drink_iso = meta.get("last_drink_at") or (active["last_event_at"] if active else None)
    inactive_h = _hours_since(last_drink_iso) if last_drink_iso else None
    age_h = _hours_since(started_iso) if started_iso else None
    expired = bool(
        (inactive_h is not None and inactive_h >= INACTIVITY_EXPIRE_HOURS)
        or (age_h is not None and age_h >= MAX_ACTIVE_SESSION_HOURS)
    )
    if not expired:
        return False
    _finalize_auto_session_and_reset(user_id, model)
    return True


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
    username = str(data.get("username", "")).strip().lower()
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
    if username:
        if len(username) < 3 or len(username) > 24:
            return jsonify({"error": "Username must be 3-24 characters"}), 400
        if any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789_" for ch in username):
            return jsonify({"error": "Username can only use a-z, 0-9, and _"}), 400
    if default_weight_lb < MIN_WEIGHT_LB or default_weight_lb > MAX_WEIGHT_LB:
        return jsonify({"error": "Weight must be between 80 and 400 lb"}), 400

    user = create_user(
        _auth_db_path(),
        email=email,
        password=password,
        display_name=display_name,
        username=username or None,
        is_male=is_male,
        default_weight_lb=default_weight_lb,
    )
    if user is None:
        return jsonify({"error": "Email or username already registered"}), 409

    flask_session.permanent = True
    flask_session[AUTH_USER_KEY] = user["id"]
    return jsonify({"ok": True, "user": user})


@app.route("/api/auth/login", methods=["POST"])
def api_auth_login():
    _ensure_auth_db()
    data = request.get_json() or {}
    email = str(data.get("email", data.get("login", ""))).strip().lower()
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


@app.route("/api/social/privacy/revoke-all", methods=["POST"])
def api_social_privacy_revoke_all():
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    _ensure_auth_db()
    revoke_all_sharing_for_user(_auth_db_path(), user_id=user_id)
    return jsonify({"ok": True})


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
    username = str(data.get("username", "")).strip().lower()
    if not email and not username:
        return jsonify({"error": "Email or username is required"}), 400
    _ensure_auth_db()
    target = find_user_by_email(_auth_db_path(), email=email) if email else find_user_by_username(_auth_db_path(), username=username)
    if target is None:
        return jsonify({"error": "User not found"}), 404
    ok, msg = send_friend_request(_auth_db_path(), from_user_id=user_id, to_user_id=target["id"])
    if not ok:
        return jsonify({"error": msg}), 400
    return jsonify({"ok": True, "message": msg})


@app.route("/api/social/user-lookup")
def api_social_user_lookup():
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    username = str(request.args.get("username", "")).strip().lower()
    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400
    _ensure_auth_db()
    target = find_user_by_username(_auth_db_path(), username=username)
    if target is None:
        return jsonify({"error": "User not found"}), 404
    if int(target["id"]) == int(user_id):
        return jsonify({"error": "That is your username"}), 400
    return jsonify(
        {
            "user": {
                "id": target["id"],
                "display_name": target["display_name"],
                "username": target["username"],
            }
        }
    )


@app.route("/api/social/invite/accept", methods=["POST"])
def api_social_invite_accept():
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    data = request.get_json() or {}
    invite_code = str(data.get("invite_code", "")).strip().upper()
    if len(invite_code) < 6:
        return jsonify({"error": "Valid invite code is required"}), 400
    _ensure_auth_db()
    inviter = find_user_by_invite_code(_auth_db_path(), invite_code=invite_code)
    if inviter is None:
        return jsonify({"error": "Invite link is invalid"}), 404
    ok, msg = add_friendship(_auth_db_path(), user_a=user_id, user_b=int(inviter["id"]))
    if not ok and msg != "Already friends.":
        return jsonify({"error": msg}), 400
    return jsonify(
        {
            "ok": True,
            "message": "Friend added." if ok else "Already friends.",
            "friend": {
                "id": inviter["id"],
                "display_name": inviter["display_name"],
                "username": inviter["username"],
            },
        }
    )


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


@app.route("/api/campus/presets")
def api_campus_presets():
    return jsonify({"items": CAMPUS_PRESETS})


@app.route("/api/favorites")
def api_favorites():
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    _ensure_auth_db()
    return jsonify({"favorites": list_favorite_drinks(_auth_db_path(), user_id=user_id, limit=6)})


@app.route("/api/setup", methods=["POST"])
def api_setup():
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()

    data = request.get_json() or {}
    weight = _clamp_float(data.get("weight_lb"), 160.0, MIN_WEIGHT_LB, MAX_WEIGHT_LB)
    is_male = _parse_bool(data.get("is_male"), default=True)
    set_session(Session(weight_lb=weight, is_male=is_male))
    _set_tracking_meta(None)
    _ensure_auth_db()
    finalize_active_auto_session(_auth_db_path(), user_id=user_id)
    return jsonify({"ok": True, "weight_lb": weight, "is_male": is_male})


@app.route("/api/drink", methods=["POST"])
def api_drink():
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()

    model = get_session()
    if model is None:
        return jsonify({"error": "Set weight and sex first"}), 400
    _expire_current_session_if_needed(user_id, model)
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
        track_favorite_drink(_auth_db_path(), user_id=user_id, catalog_id=catalog_id)
    else:
        drink_key = data.get("drink_key", "beer")
        model.add_drink_ago(hours_ago, drink_key, count)

    set_session(model)
    _record_auto_session(user_id, model, touch_last_event=True)
    return jsonify({"ok": True})


@app.route("/api/state")
def api_state():
    user_id = _require_user_id()
    if user_id is None:
        return jsonify({"authenticated": False, **_empty_state()})

    model = get_session()
    if _expire_current_session_if_needed(user_id, model):
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
    if events:
        meta = _get_tracking_meta()
        mins_since_save = _minutes_since(meta.get("last_autosave_at"))
        if mins_since_save is None or mins_since_save >= AUTOSAVE_INTERVAL_MINUTES:
            _record_auto_session(user_id, model, touch_last_event=False)
    upsert_presence(_auth_db_path(), user_id=user_id, bac_now=bac_now, drink_count=len(events))
    maybe_create_threshold_alert(_auth_db_path(), user_id=user_id, bac_now=bac_now)
    one_more_events = list(model.events_bac) + [(0.0, 14.0)]
    bac_30_if_one_more = calculations.bac_at_time(0.5, one_more_events, model.weight_lb, model.is_male)
    grams_per_hour = _estimate_rate_grams_per_hour(model.events_bac)
    drinks_per_hour = grams_per_hour / 14.0 if grams_per_hour > 0 else 0.0
    pace_curve = _project_curve_with_rate(
        model.events_bac,
        grams_per_hour=grams_per_hour,
        weight_lb=model.weight_lb,
        is_male=model.is_male,
        horizon_hours=max(0.0, model.hours_until_sober_from_now()),
    )
    confidence = _confidence_band(curve)
    markers = _event_markers(model.events_bac, weight_lb=model.weight_lb, is_male=model.is_male)
    compare_curve = _compare_curve_from_history(user_id, model, curve)
    what_if_one_now = _single_drink_projection(model.events_bac, at_hours=0.0, weight_lb=model.weight_lb, is_male=model.is_male)
    what_if_one_in_1h = _single_drink_projection(model.events_bac, at_hours=1.0, weight_lb=model.weight_lb, is_male=model.is_male)

    below_legal_time = None
    if bac_now >= 0.08:
        for t, bac in curve:
            if t >= 0 and bac < 0.08:
                below_legal_time = t
                break

    chart_data = {
        "pace_drinks_per_hour": round(drinks_per_hour, 2),
        "thresholds": [0.02, 0.05, 0.08, 0.10],
        "event_markers": markers,
        "confidence_band": confidence,
        "pace_curve": pace_curve,
        "compare_curve": compare_curve,
        "what_if_curves": {
            "one_now": what_if_one_now,
            "one_in_1h": what_if_one_in_1h,
        },
        "eta": {
            "below_legal_hours": below_legal_time,
            "sober_hours": model.hours_until_sober_from_now(),
        },
    }
    pace_prediction = {
        "bac_in_30m_if_one_more_now": round(bac_30_if_one_more, 4),
        "recommendation": (
            "Do not add another drink yet."
            if bac_30_if_one_more >= 0.08
            else "If you drink one more now, keep it to one and hydrate first."
        ),
    }

    return jsonify({
        "authenticated": True,
        "configured": True,
        "weight_lb": model.weight_lb,
        "is_male": model.is_male,
        "bac_now": bac_now,
        "curve": [{"t": t, "bac": bac} for t, bac in curve],
        "hours_until_sober_from_now": model.hours_until_sober_from_now(),
        "session_events": _session_events_payload(model),
        "drink_count": len(events),
        "total_calories": model.total_calories,
        "total_carbs_g": round(model.total_carbs_g, 1),
        "total_sugar_g": round(model.total_sugar_g, 1),
        "hangover_plan": hangover_plan,
        "drive_advice": get_drive_advice(bac_now, model.hours_until_sober_from_now()),
        "pace_prediction": pace_prediction,
        "chart_data": chart_data,
    })


@app.route("/api/session/events", methods=["PATCH"])
def api_session_events_patch():
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    model = get_session()
    if model is None:
        return jsonify({"error": "No active session"}), 400

    data = request.get_json() or {}
    try:
        index = int(data.get("index"))
    except (TypeError, ValueError):
        return jsonify({"error": "Valid index is required"}), 400

    events = list(model.events_full)
    if index < 0 or index >= len(events):
        return jsonify({"error": "Event not found"}), 404

    if bool(data.get("delete")):
        events.pop(index)
        next_model = _rebuild_model_from_events(model, events)
        set_session(next_model)
        if events:
            _record_auto_session(user_id, next_model, touch_last_event=False)
        return jsonify({"ok": True, "events": _session_events_payload(next_model)})

    try:
        hours_ago = float(data.get("hours_ago"))
        standard_drinks = float(data.get("standard_drinks"))
    except (TypeError, ValueError):
        return jsonify({"error": "hours_ago and standard_drinks are required"}), 400
    hours_ago = max(0.0, min(MAX_HOURS_AGO, hours_ago))
    standard_drinks = max(MIN_COUNT, min(MAX_COUNT, standard_drinks))

    old_t, old_grams, old_cal, old_carbs, old_sugar = events[index]
    new_grams = standard_drinks * 14.0
    ratio = (new_grams / old_grams) if old_grams > 0 else 1.0
    events[index] = (
        -hours_ago,
        new_grams,
        int(round(old_cal * ratio)),
        float(old_carbs) * ratio,
        float(old_sugar) * ratio,
    )
    next_model = _rebuild_model_from_events(model, events)
    set_session(next_model)
    _record_auto_session(user_id, next_model, touch_last_event=False)
    return jsonify({"ok": True, "events": _session_events_payload(next_model)})


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
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()

    model = get_session()
    if model is None:
        return jsonify({"ok": True})
    _finalize_auto_session_and_reset(user_id, model)
    return jsonify({"ok": True})


@app.route("/api/session/debrief")
def api_session_debrief():
    user_id = _require_user_id()
    if user_id is None:
        return _auth_required_error()
    model = get_session()
    if model is None or not model.events:
        return jsonify({"error": "No active session for debrief"}), 400
    curve = model.curve(step_hours=0.25, start_hours=min(t for t, _ in model.events), max_hours=24.0)
    peak = max((b for _, b in curve), default=0.0)
    over_limit_minutes = int(sum(15 for _, b in curve if b >= 0.08))
    suggestions = []
    if peak >= 0.10:
        suggestions.append("Peak BAC was high. Slow pace earlier and alternate water each drink.")
    if over_limit_minutes >= 120:
        suggestions.append("You spent 2+ hours above 0.08. Plan ride-home earlier next time.")
    if len(model.events) >= 6:
        suggestions.append("High drink count. Consider a hard cap before the night starts.")
    if not suggestions:
        suggestions.append("Good pacing overall. Keep hydration and transportation planning consistent.")
    return jsonify(
        {
            "peak_bac": round(peak, 4),
            "hours_until_sober_now": model.hours_until_sober_from_now(),
            "drink_count": len(model.events),
            "minutes_over_legal_limit": over_limit_minutes,
            "suggestions": suggestions,
        }
    )


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
    include_active = _parse_bool(request.args.get("include_active"), default=False)
    if session_date and not _is_valid_date_yyyy_mm_dd(session_date):
        return jsonify({"error": "date must be YYYY-MM-DD"}), 400

    items = list_user_sessions(_auth_db_path(), user_id=user_id, session_date=session_date, include_active=include_active)
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
