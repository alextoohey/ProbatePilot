from __future__ import annotations

from fastapi.testclient import TestClient

from main import app
from store.redis_client import get_estate_state, get_session_user_id, get_user_by_email


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


def test_authenticated_user_can_create_and_reload_an_additional_estate() -> None:
    client = TestClient(app)
    registration = client.post("/auth/register", json=_registration_payload("multi@example.com"))
    token = registration.json()["token"]
    headers = {"authorization": f"Bearer {token}"}

    created = client.post(
        "/estates",
        headers=headers,
        json={
            "deceasedName": "Gloria Reyes",
            "dateOfDeath": "2026-05-14",
            "relationship": "Parent",
            "role": "Executor",
            "state": "California",
            "county": "Alameda",
        },
    )

    assert created.status_code == 200
    estate = created.json()["estate"]
    assert estate["id"].startswith("est-")
    assert estate["deceasedName"] == "Gloria Reyes"
    assert estate["county"] == "Alameda"
    assert get_estate_state(estate["id"]).deceasedName == "Gloria Reyes"

    me = client.get("/auth/me", headers=headers)
    assert estate["id"] in me.json()["user"]["estateIds"]
    assert estate["id"] in {item["id"] for item in me.json()["estates"]}

    loaded = client.get(f"/estate/{estate['id']}", headers=headers)
    assert loaded.status_code == 200
    assert loaded.json()["estate"]["deceasedName"] == "Gloria Reyes"

    # Non-owners (including anonymous callers) can't read someone else's estate.
    assert client.get(f"/estate/{estate['id']}").status_code == 401
    other = client.post("/auth/register", json=_registration_payload("someone-else@example.com"))
    other_headers = {"authorization": f"Bearer {other.json()['token']}"}
    assert client.get(f"/estate/{estate['id']}", headers=other_headers).status_code == 404

    # The seeded demo estate stays readable without a session (guest/demo mode).
    assert client.get("/estate/demo-milligan").status_code == 200


def test_create_estate_requires_authentication_and_missing_estates_return_404() -> None:
    client = TestClient(app)

    unauthorized = client.post("/estates", json={"deceasedName": "Gloria Reyes"})
    assert unauthorized.status_code == 401
    assert client.get("/estate/est-does-not-exist").status_code == 401

    registration = client.post("/auth/register", json=_registration_payload("missing-estate@example.com"))
    headers = {"authorization": f"Bearer {registration.json()['token']}"}
    assert client.get("/estate/est-does-not-exist", headers=headers).status_code == 404
