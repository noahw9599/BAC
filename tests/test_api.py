"""API-level tests for the Flask app."""

import pytest

from app import app


@pytest.fixture(autouse=True)
def feedback_db_env(tmp_path, monkeypatch):
    db_path = tmp_path / "feedback.db"
    monkeypatch.setenv("FEEDBACK_DB_PATH", str(db_path))
    monkeypatch.setenv("ADMIN_TOKEN", "test-token")
    yield


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_healthz(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.get_json() == {"ok": True}


def test_state_unconfigured(client):
    res = client.get("/api/state")
    assert res.status_code == 200
    data = res.get_json()
    assert data["configured"] is False
    assert data["drink_count"] == 0


def test_setup_clamps_and_parses(client):
    res = client.post("/api/setup", json={"weight_lb": "999", "is_male": "false"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["weight_lb"] == 400.0
    assert data["is_male"] is False


def test_drink_requires_setup(client):
    res = client.post("/api/drink", json={"catalog_id": "bud-light", "count": 1, "hours_ago": 0})
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_drink_and_state_roundtrip(client):
    client.post("/api/setup", json={"weight_lb": 170, "is_male": True})

    add = client.post("/api/drink", json={"catalog_id": "bud-light", "count": 2, "hours_ago": 1})
    assert add.status_code == 200

    state = client.get("/api/state?hours_until_target=10")
    assert state.status_code == 200
    data = state.get_json()
    assert data["configured"] is True
    assert data["drink_count"] == 1
    assert data["total_calories"] == 220
    assert data["hangover_plan"] is not None


def test_reset_keeps_profile_and_clears_events(client):
    client.post("/api/setup", json={"weight_lb": 150, "is_male": True})
    client.post("/api/drink", json={"drink_key": "beer", "count": 1, "hours_ago": 0})

    reset = client.post("/api/reset")
    assert reset.status_code == 200

    state = client.get("/api/state")
    data = state.get_json()
    assert data["configured"] is True
    assert data["drink_count"] == 0


def test_sessions_are_isolated_per_client():
    app.config["TESTING"] = True
    c1 = app.test_client()
    c2 = app.test_client()

    c1.post("/api/setup", json={"weight_lb": 160, "is_male": True})
    c1.post("/api/drink", json={"drink_key": "beer", "count": 1, "hours_ago": 0})

    c2_state = c2.get("/api/state").get_json()
    c1_state = c1.get("/api/state").get_json()

    assert c1_state["configured"] is True
    assert c1_state["drink_count"] == 1
    assert c2_state["configured"] is False


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
