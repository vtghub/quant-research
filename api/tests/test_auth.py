from __future__ import annotations


def test_register_and_login(client) -> None:
    resp = client.post("/auth/register", json={"email": "a@example.com", "password": "password123"})
    assert resp.status_code == 201
    assert resp.json()["email"] == "a@example.com"

    resp = client.post("/auth/login", data={"username": "a@example.com", "password": "password123"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "a@example.com"


def test_duplicate_email_rejected(client) -> None:
    client.post("/auth/register", json={"email": "dup@example.com", "password": "password123"})
    resp = client.post("/auth/register", json={"email": "dup@example.com", "password": "password123"})
    assert resp.status_code == 409


def test_wrong_password_rejected(client) -> None:
    client.post("/auth/register", json={"email": "b@example.com", "password": "password123"})
    resp = client.post("/auth/login", data={"username": "b@example.com", "password": "wrong"})
    assert resp.status_code == 401


def test_unknown_email_rejected(client) -> None:
    resp = client.post("/auth/login", data={"username": "nobody@example.com", "password": "whatever"})
    assert resp.status_code == 401


def test_me_requires_auth(client) -> None:
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_rejects_garbage_token(client) -> None:
    resp = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_short_password_rejected(client) -> None:
    resp = client.post("/auth/register", json={"email": "c@example.com", "password": "short"})
    assert resp.status_code == 422


def test_invalid_email_rejected(client) -> None:
    resp = client.post("/auth/register", json={"email": "not-an-email", "password": "password123"})
    assert resp.status_code == 422
