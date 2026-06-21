from __future__ import annotations

from fastapi.testclient import TestClient

from main import app
from store.redis_client import get_session_user_id, get_user_by_email


def _registration_payload(email: str = "dana@example.com") -> dict[str, object]:
    return {
        "name": "Dana Milligan",
        "email": email,
        "password": "correct horse battery staple",
        "phone": "555-1212",
        "deceasedName": "Robert A. Milligan",
        "dateOfDeath": "2026-06-03",
        "relationship": "Daughter",
        "state": "California",
        "county": "Alameda",
        "hasWill": "yes",
    }


def test_register_creates_user_estate_and_session_without_exposing_password_hash() -> None:
    client = TestClient(app)

    response = client.post("/auth/register", json=_registration_payload("Dana@Example.com"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["token"]
    assert payload["user"]["email"] == "dana@example.com"
    assert "passwordHash" not in payload["user"]
    assert payload["estate"]["deceasedName"] == "Robert A. Milligan"
    assert payload["estate"]["executor"] == {"name": "Dana Milligan", "email": "dana@example.com"}

    user = get_user_by_email("dana@example.com")
    assert user is not None
    assert payload["estate"]["id"] in user.estateIds
    assert get_session_user_id(payload["token"]) == user.id


def test_auth_login_me_duplicate_register_and_logout_flow() -> None:
    client = TestClient(app)
    register_response = client.post("/auth/register", json=_registration_payload())
    token = register_response.json()["token"]

    duplicate = client.post("/auth/register", json=_registration_payload())
    assert duplicate.status_code == 409

    bad_login = client.post("/auth/login", json={"email": "dana@example.com", "password": "wrong password"})
    assert bad_login.status_code == 401

    login = client.post(
        "/auth/login",
        json={"email": "DANA@example.com", "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    login_payload = login.json()
    assert login_payload["token"] != token
    assert login_payload["user"]["estateIds"] == register_response.json()["user"]["estateIds"]
    assert login_payload.get("estate") is None

    me = client.get("/auth/me", headers={"authorization": f"Bearer {login_payload['token']}"})
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "dana@example.com"
    assert me.json()["estates"][0]["id"] == login_payload["user"]["estateIds"][0]

    logout = client.post("/auth/logout", headers={"authorization": f"Bearer {login_payload['token']}"})
    assert logout.status_code == 200
    assert get_session_user_id(login_payload["token"]) is None

    after_logout = client.get("/auth/me", headers={"authorization": f"Bearer {login_payload['token']}"})
    assert after_logout.status_code == 401


def test_me_rejects_missing_or_malformed_authorization() -> None:
    client = TestClient(app)

    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"authorization": "Token nope"}).status_code == 401
