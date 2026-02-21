"""API-level tests for the Flask app."""

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


def test_register_trims_password(client):
    reg = client.post(
        "/api/auth/register",
        json={
            "email": "trimreg@example.edu",
            "password": " password123 ",
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
            "display_name": "Bad2",
            "gender": "female",
            "default_weight_lb": 40,
        },
    )
    assert bad_weight.status_code == 400


def test_sessions_are_isolated_per_client():
    app.config["TESTING"] = True
    c1 = app.test_client()
    c2 = app.test_client()

    c1.post(
        "/api/auth/register",
        json={
            "email": "a@example.edu",
            "password": "password123",
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
