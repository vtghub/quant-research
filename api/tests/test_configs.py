from __future__ import annotations

import pytest

VALID_CONFIG = {
    "name": "test",
    "universe": {"symbols": ["AAA", "BBB"], "start": "2020-01-01", "end": "2021-01-01", "primary_source": "yfinance"},
    "signals": [{"name": "momentum", "alias": "mom"}],
    "strategy": {"name": "rank_weighted_long_short", "signals": ["mom"]},
}


@pytest.fixture
def auth_headers(client):
    client.post("/auth/register", json={"email": "cfg@example.com", "password": "password123"})
    resp = client.post("/auth/login", data={"username": "cfg@example.com", "password": "password123"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_create_and_get_config(client, auth_headers) -> None:
    resp = client.post("/configs", json={"name": "mine", "config_json": VALID_CONFIG}, headers=auth_headers)
    assert resp.status_code == 201
    config_id = resp.json()["id"]

    resp = client.get(f"/configs/{config_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "mine"


def test_invalid_config_rejected(client, auth_headers) -> None:
    bad = {**VALID_CONFIG, "strategy": {"name": "rank_weighted_long_short", "signals": ["nope"]}}
    resp = client.post("/configs", json={"name": "bad", "config_json": bad}, headers=auth_headers)
    assert resp.status_code == 422
    assert "unknown signal alias" in resp.text


def test_invalid_config_bad_universe_dates_rejected(client, auth_headers) -> None:
    bad = {**VALID_CONFIG, "universe": {**VALID_CONFIG["universe"], "start": "2022-01-01", "end": "2021-01-01"}}
    resp = client.post("/configs", json={"name": "bad-dates", "config_json": bad}, headers=auth_headers)
    assert resp.status_code == 422


def test_list_configs_scoped_to_owner(client) -> None:
    client.post("/auth/register", json={"email": "u1@example.com", "password": "password123"})
    t1 = client.post("/auth/login", data={"username": "u1@example.com", "password": "password123"}).json()[
        "access_token"
    ]
    client.post("/auth/register", json={"email": "u2@example.com", "password": "password123"})
    t2 = client.post("/auth/login", data={"username": "u2@example.com", "password": "password123"}).json()[
        "access_token"
    ]

    client.post(
        "/configs", json={"name": "u1 config", "config_json": VALID_CONFIG}, headers={"Authorization": f"Bearer {t1}"}
    )

    resp = client.get("/configs", headers={"Authorization": f"Bearer {t2}"})
    assert resp.json() == []
    resp = client.get("/configs", headers={"Authorization": f"Bearer {t1}"})
    assert len(resp.json()) == 1


def test_update_and_delete_config(client, auth_headers) -> None:
    resp = client.post("/configs", json={"name": "mine", "config_json": VALID_CONFIG}, headers=auth_headers)
    config_id = resp.json()["id"]

    resp = client.put(f"/configs/{config_id}", json={"name": "renamed"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "renamed"

    resp = client.delete(f"/configs/{config_id}", headers=auth_headers)
    assert resp.status_code == 204
    resp = client.get(f"/configs/{config_id}", headers=auth_headers)
    assert resp.status_code == 404


def test_cannot_access_other_users_config(client) -> None:
    client.post("/auth/register", json={"email": "owner@example.com", "password": "password123"})
    t_owner = client.post("/auth/login", data={"username": "owner@example.com", "password": "password123"}).json()[
        "access_token"
    ]
    client.post("/auth/register", json={"email": "intruder@example.com", "password": "password123"})
    t_intruder = client.post(
        "/auth/login", data={"username": "intruder@example.com", "password": "password123"}
    ).json()["access_token"]

    resp = client.post(
        "/configs",
        json={"name": "secret", "config_json": VALID_CONFIG},
        headers={"Authorization": f"Bearer {t_owner}"},
    )
    config_id = resp.json()["id"]

    resp = client.get(f"/configs/{config_id}", headers={"Authorization": f"Bearer {t_intruder}"})
    assert resp.status_code == 404

    resp = client.delete(f"/configs/{config_id}", headers={"Authorization": f"Bearer {t_intruder}"})
    assert resp.status_code == 404


def test_configs_require_auth(client) -> None:
    resp = client.get("/configs")
    assert resp.status_code == 401
