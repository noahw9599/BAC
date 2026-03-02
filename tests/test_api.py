"""API-level tests for the Flask app."""

import csv
import io

import pytest

from app import app


@pytest.fixture(autouse=True)
def env_setup(tmp_path, monkeypatch):
    monkeypatch.setenv("FEEDBACK_DB_PATH", str(tmp_path / "feedback.db"))
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("ADMIN_TOKEN", "test-token")
    yield


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def register(
    client,
    email="student@example.edu",
    password="password123",
    name="Student",
    gender="male",
    default_weight_lb=160,
):
    res = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
            "confirm_password": password,
            "display_name": name,
            "gender": gender,
            "default_weight_lb": default_weight_lb,
        },
    )
    assert res.status_code == 200
    return res.get_json()["user"]


def test_healthz(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.get_json() == {"ok": True}


def test_privacy_page_is_public(client):
    res = client.get("/privacy")
    assert res.status_code == 200
    assert "Privacy Policy" in res.get_data(as_text=True)


def test_admin_db_check_requires_token(client):
    denied = client.get("/api/admin/db-check")
    assert denied.status_code == 403

    ok = client.get("/api/admin/db-check?token=test-token")
    assert ok.status_code == 200
    body = ok.get_json()
    assert body["ok"] is True
    assert body["checks"]["auth_db_init_ok"] is True
    assert body["checks"]["feedback_db_init_ok"] is True


def test_state_unconfigured_unauthenticated(client):
    res = client.get("/api/state")
    assert res.status_code == 200
    data = res.get_json()
    assert data["authenticated"] is False
    assert data["configured"] is False


def test_setup_requires_auth(client):
    res = client.post("/api/setup", json={"weight_lb": 160, "is_male": True})
    assert res.status_code == 401


def test_setup_clamps_and_parses(client):
    register(client)
    res = client.post("/api/setup", json={"weight_lb": "999", "is_male": "false"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["weight_lb"] == 400.0
    assert data["is_male"] is False


def test_drink_requires_setup(client):
    register(client)
    res = client.post("/api/drink", json={"catalog_id": "bud-light", "count": 1, "hours_ago": 0})
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_drink_and_state_roundtrip(client):
    register(client)
    client.post("/api/setup", json={"weight_lb": 170, "is_male": True})

    add = client.post("/api/drink", json={"catalog_id": "bud-light", "count": 2, "hours_ago": 1})
    assert add.status_code == 200

    state = client.get("/api/state?hours_until_target=10")
    assert state.status_code == 200
    data = state.get_json()
    assert data["authenticated"] is True
    assert data["configured"] is True
    assert data["drink_count"] == 1
    assert data["total_calories"] == 220
    assert data["hangover_plan"] is not None
    assert data["drive_advice"] is not None
    assert "status" in data["drive_advice"]


def test_drink_sip_mode_uses_midpoint_time(client):
    register(client)
    client.post("/api/setup", json={"weight_lb": 170, "is_male": True})
    add = client.post("/api/drink", json={"catalog_id": "bud-light", "count": 1, "hours_ago": 0, "sip_minutes": 30})
    assert add.status_code == 200

    state = client.get("/api/state")
    assert state.status_code == 200
    events = state.get_json()["session_events"]
    assert len(events) == 1
    assert events[0]["hours_ago"] == pytest.approx(0.25, abs=0.02)


def test_drink_rejects_invalid_sip_mode(client):
    register(client)
    client.post("/api/setup", json={"weight_lb": 170, "is_male": True})
    add = client.post("/api/drink", json={"catalog_id": "bud-light", "count": 1, "hours_ago": 0, "sip_minutes": 20})
    assert add.status_code == 400
    assert "sip_minutes" in add.get_json()["error"]


def test_reset_keeps_profile_and_clears_events(client):
    register(client)
    client.post("/api/setup", json={"weight_lb": 150, "is_male": True})
    client.post("/api/drink", json={"drink_key": "beer", "count": 1, "hours_ago": 0})

    reset = client.post("/api/reset")
    assert reset.status_code == 200

    state = client.get("/api/state")
    data = state.get_json()
    assert data["configured"] is True
    assert data["drink_count"] == 0


def test_auth_login_logout(client):
    register(client, email="user1@example.edu")

    me = client.get("/api/auth/me").get_json()
    assert me["authenticated"] is True

    client.post("/api/auth/logout")
    me_after = client.get("/api/auth/me").get_json()
    assert me_after["authenticated"] is False

    login = client.post("/api/auth/login", json={"email": "user1@example.edu", "password": "password123"})
    assert login.status_code == 200


def test_login_allows_trimmed_password_input(client):
    register(client, email="trim@example.edu", password="password123")
    client.post("/api/auth/logout")
    login = client.post("/api/auth/login", json={"email": "trim@example.edu", "password": " password123 "})
    assert login.status_code == 200


def test_login_allows_username_identifier(client):
    user = register(client, email="username-login@example.edu", password="password123", name="User Login")
    client.post("/api/auth/logout")
    login = client.post("/api/auth/login", json={"email": user["username"], "password": "password123"})
    assert login.status_code == 200


def test_register_trims_password(client):
    reg = client.post(
        "/api/auth/register",
        json={
            "email": "trimreg@example.edu",
            "password": " password123 ",
            "confirm_password": " password123 ",
            "display_name": "TrimReg",
            "gender": "male",
            "default_weight_lb": 165,
        },
    )
    assert reg.status_code == 200
    client.post("/api/auth/logout")
    login = client.post("/api/auth/login", json={"email": "trimreg@example.edu", "password": "password123"})
    assert login.status_code == 200


def test_saved_sessions_roundtrip(client):
    register(client)
    client.post("/api/setup", json={"weight_lb": 160, "is_male": True})
    client.post("/api/drink", json={"drink_key": "beer", "count": 2, "hours_ago": 0})

    save = client.post("/api/session/save", json={"name": "Friday"})
    assert save.status_code == 200
    saved_id = save.get_json()["session_id"]

    listing = client.get("/api/session/list")
    assert listing.status_code == 200
    items = listing.get_json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "Friday"

    client.post("/api/reset")
    after_reset = client.get("/api/state").get_json()
    assert after_reset["drink_count"] == 0

    load = client.post("/api/session/load", json={"session_id": saved_id})
    assert load.status_code == 200

    reloaded = client.get("/api/state").get_json()
    assert reloaded["drink_count"] == 1

    dates = client.get("/api/session/dates")
    assert dates.status_code == 200
    date_items = dates.get_json()["items"]
    assert len(date_items) >= 1
    session_date = date_items[0]["session_date"]

    by_date = client.get(f"/api/session/list?date={session_date}")
    assert by_date.status_code == 200
    assert by_date.get_json()["items"][0]["session_date"] == session_date


def test_session_export_requires_auth(client):
    res = client.get("/api/session/export.csv")
    assert res.status_code == 401


def test_session_export_csv_contains_saved_rows(client):
    register(client, email="csv@example.edu", name="Csv User")
    client.post("/api/setup", json={"weight_lb": 165, "is_male": True})
    client.post("/api/drink", json={"drink_key": "beer", "count": 2, "hours_ago": 0})
    client.post("/api/session/save", json={"name": "CSV Night"})

    exported = client.get("/api/session/export.csv")
    assert exported.status_code == 200
    assert exported.mimetype == "text/csv"
    assert "attachment; filename=" in exported.headers.get("Content-Disposition", "")

    text = exported.get_data(as_text=True)
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) >= 1
    assert rows[0]["name"] == "CSV Night"
    assert rows[0]["drink_count"] == "1"
    assert rows[0]["is_active"] == "false"


def test_favorites_persist_per_user(client):
    register(client, email="fav@example.edu", password="password123")
    client.post("/api/setup", json={"weight_lb": 160, "is_male": True})
    client.post("/api/drink", json={"catalog_id": "bud-light", "count": 1, "hours_ago": 0})
    client.post("/api/drink", json={"catalog_id": "truly", "count": 1, "hours_ago": 0})
    client.post("/api/drink", json={"catalog_id": "vodka-soda", "count": 1, "hours_ago": 0})

    favs = client.get("/api/favorites")
    assert favs.status_code == 200
    ids = favs.get_json()["favorites"]
    assert ids[0] == "vodka-soda"
    assert "bud-light" in ids

    client.post("/api/auth/logout")
    login = client.post("/api/auth/login", json={"email": "fav@example.edu", "password": "password123"})
    assert login.status_code == 200

    favs_again = client.get("/api/favorites")
    assert favs_again.status_code == 200
    assert favs_again.get_json()["favorites"][0] == "vodka-soda"


def test_register_requires_gender_and_weight(client):
    bad_gender = client.post(
        "/api/auth/register",
        json={
            "email": "bad1@example.edu",
            "password": "password123",
            "confirm_password": "password123",
            "display_name": "Bad1",
            "gender": "unknown",
            "default_weight_lb": 160,
        },
    )
    assert bad_gender.status_code == 400

    bad_weight = client.post(
        "/api/auth/register",
        json={
            "email": "bad2@example.edu",
            "password": "password123",
            "confirm_password": "password123",
            "display_name": "Bad2",
            "gender": "female",
            "default_weight_lb": 40,
        },
    )
    assert bad_weight.status_code == 400


def test_register_requires_matching_confirm_password(client):
    bad = client.post(
        "/api/auth/register",
        json={
            "email": "nomatch@example.edu",
            "password": "password123",
            "confirm_password": "password456",
            "display_name": "NoMatch",
            "gender": "male",
            "default_weight_lb": 160,
        },
    )
    assert bad.status_code == 400


def test_account_profile_update(client):
    user = register(client, email="profile-update@example.edu", name="ProfileUser")
    update = client.post(
        "/api/account/profile",
        json={
            "display_name": "Updated Name",
            "username": "updated_name",
            "gender": "female",
            "default_weight_lb": 145,
        },
    )
    assert update.status_code == 200
    body = update.get_json()
    assert body["ok"] is True
    assert body["user"]["display_name"] == "Updated Name"
    assert body["user"]["username"] == "updated_name"
    assert body["user"]["is_male"] is False

    client.post("/api/auth/logout")
    login_by_username = client.post("/api/auth/login", json={"email": "updated_name", "password": "password123"})
    assert login_by_username.status_code == 200


def test_account_privacy_and_emergency_contacts(client):
    register(client, email="privacy@example.edu", name="PrivacyUser")

    summary = client.get("/api/account/privacy-summary")
    assert summary.status_code == 200
    body = summary.get_json()
    assert body["ok"] is True
    assert body["summary"]["share_with_friends"] is False

    add = client.post("/api/account/emergency-contacts", json={"name": "Mom", "phone": "555-0101"})
    assert add.status_code == 200
    contact_id = add.get_json()["contact"]["id"]

    listing = client.get("/api/account/emergency-contacts")
    assert listing.status_code == 200
    contacts = listing.get_json()["contacts"]
    assert len(contacts) == 1
    assert contacts[0]["name"] == "Mom"

    delete = client.delete(f"/api/account/emergency-contacts/{contact_id}")
    assert delete.status_code == 200
    listing_again = client.get("/api/account/emergency-contacts").get_json()
    assert listing_again["contacts"] == []


def test_account_delete_requires_password_and_removes_login(client):
    register(client, email="delete-me@example.edu", password="password123", name="Delete Me")
    bad = client.post("/api/account/delete", json={"password": "wrong", "confirm_text": "DELETE"})
    assert bad.status_code == 401

    missing_confirm = client.post("/api/account/delete", json={"password": "password123", "confirm_text": "NO"})
    assert missing_confirm.status_code == 400

    ok = client.post("/api/account/delete", json={"password": "password123", "confirm_text": "DELETE"})
    assert ok.status_code == 200
    assert ok.get_json()["ok"] is True

    me = client.get("/api/auth/me").get_json()
    assert me["authenticated"] is False

    login = client.post("/api/auth/login", json={"email": "delete-me@example.edu", "password": "password123"})
    assert login.status_code == 401


def test_session_event_delete_and_restore(client):
    register(client, email="restore@example.edu", name="RestoreUser")
    client.post("/api/setup", json={"weight_lb": 170, "is_male": True})
    client.post("/api/drink", json={"drink_key": "beer", "count": 1, "hours_ago": 0})

    before = client.get("/api/state").get_json()
    assert len(before["session_events"]) == 1

    deleted = client.patch("/api/session/events", json={"index": 0, "delete": True})
    assert deleted.status_code == 200
    deleted_body = deleted.get_json()
    assert deleted_body["deleted_event"]["standard_drinks"] == 1.0

    after_delete = client.get("/api/state").get_json()
    assert len(after_delete["session_events"]) == 0

    restored = client.patch(
        "/api/session/events",
        json={"index": 0, "restore_event": deleted_body["deleted_event"]},
    )
    assert restored.status_code == 200

    after_restore = client.get("/api/state").get_json()
    assert len(after_restore["session_events"]) == 1


def test_sessions_are_isolated_per_client():
    app.config["TESTING"] = True
    c1 = app.test_client()
    c2 = app.test_client()

    c1.post(
        "/api/auth/register",
        json={
            "email": "a@example.edu",
            "password": "password123",
            "confirm_password": "password123",
            "display_name": "A",
            "gender": "male",
            "default_weight_lb": 160,
        },
    )
    c1.post("/api/setup", json={"weight_lb": 160, "is_male": True})
    c1.post("/api/drink", json={"drink_key": "beer", "count": 1, "hours_ago": 0})

    c2_state = c2.get("/api/state").get_json()
    c1_state = c1.get("/api/state").get_json()

    assert c1_state["authenticated"] is True
    assert c1_state["drink_count"] == 1
    assert c2_state["authenticated"] is False


def test_feedback_submit_and_recent_requires_token(client):
    res = client.post(
        "/api/feedback",
        json={"message": "Great pace coach", "rating": 5, "contact": "tester@example.com"},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["ok"] is True
    assert body["feedback_id"] >= 1

    forbidden = client.get("/api/feedback/recent")
    assert forbidden.status_code == 403

    recent = client.get("/api/feedback/recent?token=test-token")
    assert recent.status_code == 200
    items = recent.get_json()["items"]
    assert len(items) == 1
    assert items[0]["message"] == "Great pace coach"
    assert items[0]["rating"] == 5


def test_feedback_validation(client):
    missing = client.post("/api/feedback", json={"message": ""})
    assert missing.status_code == 400

    bad_rating = client.post("/api/feedback", json={"message": "x", "rating": 99})
    assert bad_rating.status_code == 400


def test_drive_advice_do_not_drive_when_high_bac(client):
    register(client)
    client.post("/api/setup", json={"weight_lb": 160, "is_male": True})
    client.post("/api/drink", json={"drink_key": "liquor", "count": 4, "hours_ago": 0})

    state = client.get("/api/state").get_json()
    assert state["drive_advice"]["status"] == "do_not_drive"


def test_drive_advice_ok_when_no_drinks_logged(client):
    register(client, email="nodrinks@example.edu")
    client.post("/api/setup", json={"weight_lb": 160, "is_male": True})
    state = client.get("/api/state").get_json()
    assert state["drive_advice"]["status"] == "ok"
    assert state["bac_now"] == 0


def test_social_friend_request_and_feed_flow():
    app.config["TESTING"] = True
    a = app.test_client()
    b = app.test_client()

    register(a, email="alice@example.edu", name="Alice")
    register(b, email="bob@example.edu", name="Bob")

    req = a.post("/api/social/request", json={"email": "bob@example.edu"})
    assert req.status_code == 200

    status_b = b.get("/api/social/status")
    assert status_b.status_code == 200
    incoming = status_b.get_json()["incoming_requests"]
    assert len(incoming) == 1
    request_id = incoming[0]["request_id"]

    accept = b.post("/api/social/request/respond", json={"request_id": request_id, "action": "accept"})
    assert accept.status_code == 200

    # Bob opts in to sharing and logs a session state.
    b.post("/api/social/share", json={"enabled": True})
    b.post("/api/setup", json={"weight_lb": 170, "is_male": True})
    b.post("/api/drink", json={"drink_key": "beer", "count": 1, "hours_ago": 0})
    b.get("/api/state")

    feed = a.get("/api/social/feed")
    assert feed.status_code == 200
    items = feed.get_json()["items"]
    assert len(items) >= 1
    assert items[0]["display_name"] == "Bob"


def test_group_safety_flow():
    app.config["TESTING"] = True
    a = app.test_client()
    b = app.test_client()
    register(a, email="g1@example.edu", name="G1")
    register(b, email="g2@example.edu", name="G2")

    created = a.post("/api/social/groups/create", json={"name": "Friday Crew"})
    assert created.status_code == 200
    invite_code = created.get_json()["group"]["invite_code"]

    joined = b.post("/api/social/groups/join", json={"invite_code": invite_code})
    assert joined.status_code == 200

    groups_b = b.get("/api/social/groups").get_json()["items"]
    group_id = groups_b[0]["id"]

    b.post(f"/api/social/groups/{group_id}/share", json={"enabled": True})
    b.post("/api/setup", json={"weight_lb": 160, "is_male": True})
    b.post("/api/drink", json={"drink_key": "beer", "count": 1, "hours_ago": 0})
    b.post(f"/api/social/groups/{group_id}/location", json={"location_note": "Main street"})

    snap = a.get(f"/api/social/groups/{group_id}")
    assert snap.status_code == 200
    members = snap.get_json()["members"]
    assert any(m["display_name"] == "G2" for m in members)

    # Guardian link creation and public snapshot.
    gl = a.post(f"/api/social/groups/{group_id}/guardian-links", json={"label": "Mom", "receive_alerts": True})
    assert gl.status_code == 200
    token = gl.get_json()["item"]["token"]

    public_snap = a.get(f"/api/guardian/{token}")
    assert public_snap.status_code == 200
    assert public_snap.get_json()["group"]["name"] == "Friday Crew"

    links = a.get(f"/api/social/groups/{group_id}/guardian-links")
    assert links.status_code == 200
    link_id = links.get_json()["items"][0]["id"]

    mute = a.post(f"/api/social/groups/{group_id}/guardian-links/{link_id}/alerts", json={"enabled": False})
    assert mute.status_code == 200

    revoke = a.post(f"/api/social/groups/{group_id}/guardian-links/{link_id}/revoke")
    assert revoke.status_code == 200
    public_after = a.get(f"/api/guardian/{token}")
    assert public_after.status_code == 404


def test_group_buddy_and_emergency_alert_flow():
    app.config["TESTING"] = True
    owner = app.test_client()
    member = app.test_client()
    register(owner, email="buddy-owner@example.edu", name="Owner")
    register(member, email="buddy-member@example.edu", name="Member")

    created = owner.post("/api/social/groups/create", json={"name": "Safety Crew"})
    assert created.status_code == 200
    group_id = created.get_json()["group"]["id"]
    invite_code = created.get_json()["group"]["invite_code"]

    joined = member.post("/api/social/groups/join", json={"invite_code": invite_code})
    assert joined.status_code == 200

    snap = owner.get(f"/api/social/groups/{group_id}").get_json()
    owner_id = next(m["user_id"] for m in snap["members"] if m["display_name"] == "Owner")
    member_id = next(m["user_id"] for m in snap["members"] if m["display_name"] == "Member")

    pair = owner.post(f"/api/social/groups/{group_id}/buddy", json={"user_a": owner_id, "user_b": member_id})
    assert pair.status_code == 200
    snap_after_pair = owner.get(f"/api/social/groups/{group_id}").get_json()
    owner_row = next(m for m in snap_after_pair["members"] if m["user_id"] == owner_id)
    assert owner_row["buddy_user_id"] == member_id

    status_update = owner.post(f"/api/social/groups/{group_id}/location", json={"preset": "home_safe"})
    assert status_update.status_code == 200

    emergency = owner.post(
        f"/api/social/groups/{group_id}/check",
        json={"target_user_id": member_id, "kind": "emergency"},
    )
    assert emergency.status_code == 200


def test_campus_presets_available(client):
    res = client.get("/api/campus/presets")
    assert res.status_code == 200
    items = res.get_json()["items"]
    assert len(items) >= 1
    assert {"id", "name", "emergency_phone"}.issubset(items[0].keys())


def test_session_debrief_requires_active_session(client):
    register(client)
    no_data = client.get("/api/session/debrief")
    assert no_data.status_code == 400

    client.post("/api/setup", json={"weight_lb": 160, "is_male": True})
    client.post("/api/drink", json={"drink_key": "beer", "count": 2, "hours_ago": 0})
    res = client.get("/api/session/debrief")
    assert res.status_code == 200
    body = res.get_json()
    assert "peak_bac" in body
    assert "suggestions" in body


def test_privacy_revoke_all_disables_group_sharing_and_guardians():
    app.config["TESTING"] = True
    a = app.test_client()
    b = app.test_client()
    register(a, email="owner@example.edu", name="Owner")
    register(b, email="member@example.edu", name="Member")

    created = a.post("/api/social/groups/create", json={"name": "Safety Crew"})
    group_id = created.get_json()["group"]["id"]
    invite_code = created.get_json()["group"]["invite_code"]
    b.post("/api/social/groups/join", json={"invite_code": invite_code})

    gl = a.post(f"/api/social/groups/{group_id}/guardian-links", json={"label": "Parent", "receive_alerts": True})
    token = gl.get_json()["item"]["token"]
    assert a.get(f"/api/guardian/{token}").status_code == 200

    revoke = a.post("/api/social/privacy/revoke-all")
    assert revoke.status_code == 200

    snap = a.get(f"/api/social/groups/{group_id}")
    assert snap.status_code == 200
    me = next(m for m in snap.get_json()["members"] if m["display_name"] == "Owner")
    assert me["share_enabled"] is False
    assert a.get(f"/api/guardian/{token}").status_code == 404


def test_register_returns_username_and_invite_code(client):
    user = register(client, email="named@example.edu", name="Named Person")
    assert user["username"]
    assert user["invite_code"]


def test_social_lookup_and_request_by_username():
    app.config["TESTING"] = True
    a = app.test_client()
    b = app.test_client()
    register(a, email="lookup-a@example.edu", name="LookupA")
    b_user = register(b, email="lookup-b@example.edu", name="LookupB")

    lookup = a.get(f"/api/social/user-lookup?username={b_user['username']}")
    assert lookup.status_code == 200
    assert lookup.get_json()["user"]["id"] == b_user["id"]

    req = a.post("/api/social/request", json={"username": b_user["username"]})
    assert req.status_code == 200


def test_invite_link_accept_adds_friendship():
    app.config["TESTING"] = True
    a = app.test_client()
    b = app.test_client()
    inviter = register(a, email="inviter@example.edu", name="Inviter")
    register(b, email="joiner@example.edu", name="Joiner")

    accept = b.post("/api/social/invite/accept", json={"invite_code": inviter["invite_code"]})
    assert accept.status_code == 200

    friends = b.get("/api/social/status").get_json()["friends"]
    assert any(f["id"] == inviter["id"] for f in friends)


def test_auto_session_expires_and_moves_to_history(client):
    register(client, email="auto@example.edu", name="Auto")
    client.post("/api/setup", json={"weight_lb": 160, "is_male": True})
    client.post("/api/drink", json={"drink_key": "beer", "count": 1, "hours_ago": 0})

    active = client.get("/api/session/list?include_active=1")
    assert active.status_code == 200
    active_items = active.get_json()["items"]
    assert len(active_items) == 1
    assert active_items[0]["is_active"] is True
    assert active_items[0]["is_auto"] is True

    default_history_before = client.get("/api/session/list").get_json()["items"]
    assert len(default_history_before) == 0

    with client.session_transaction() as sess:
        sess["tracking_meta"] = {
            "session_started_at": "2020-01-01T00:00:00",
            "last_drink_at": "2020-01-01T00:10:00",
            "last_autosave_at": "2020-01-01T00:10:00",
        }

    state_after = client.get("/api/state")
    assert state_after.status_code == 200
    assert state_after.get_json()["drink_count"] == 0

    history_after = client.get("/api/session/list")
    assert history_after.status_code == 200
    items = history_after.get_json()["items"]
    assert len(items) == 1
    assert items[0]["is_auto"] is True
    assert items[0]["is_active"] is False


def test_session_event_edit_and_delete(client):
    register(client, email="edit-events@example.edu", name="EditEvents")
    client.post("/api/setup", json={"weight_lb": 170, "is_male": True})
    client.post("/api/drink", json={"drink_key": "beer", "count": 1, "hours_ago": 1})
    client.post("/api/drink", json={"drink_key": "beer", "count": 1, "hours_ago": 0})

    state = client.get("/api/state").get_json()
    assert len(state["session_events"]) == 2

    edit = client.patch("/api/session/events", json={"index": 0, "hours_ago": 2, "standard_drinks": 2})
    assert edit.status_code == 200
    edited_state = client.get("/api/state").get_json()
    assert len(edited_state["session_events"]) == 2
    assert edited_state["session_events"][0]["standard_drinks"] == 2.0

    delete = client.patch("/api/session/events", json={"index": 1, "delete": True})
    assert delete.status_code == 200
    final_state = client.get("/api/state").get_json()
    assert len(final_state["session_events"]) == 1
