"""API-level tests for the Flask app."""

import pytest

from app import app, set_session


@pytest.fixture(autouse=True)
def clear_session():
    set_session(None)
    yield
    set_session(None)


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