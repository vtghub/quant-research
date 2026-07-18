from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant_research.core.exceptions import DataSourceError
from quant_research.core.registries import DATA_SOURCE_REGISTRY

SYNTHETIC_CONFIG_TEMPLATE = {
    "name": "run_test",
    "universe": {
        "symbols": ["AAA", "BBB"],
        "start": "2022-01-01",
        "end": "2022-06-01",
        "primary_source": "api_test_fake_source",
    },
    "signals": [{"name": "momentum", "alias": "mom", "params": {"lookback": 20, "skip_recent": 2}}],
    "strategy": {"name": "rank_weighted_long_short", "signals": ["mom"]},
    "report": {"formats": ["markdown"]},
}


@pytest.fixture(autouse=True)
def registered_fake_source():
    dates = pd.bdate_range("2021-01-01", "2022-12-31")  # comfortably covers SYNTHETIC_CONFIG_TEMPLATE's range
    rng = np.random.default_rng(3)
    frames = []
    for symbol in ("AAA", "BBB"):
        prices = 100 * (1 + rng.normal(0, 0.01, len(dates))).cumprod()
        frames.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "symbol": symbol,
                    "open": prices,
                    "high": prices * 1.001,
                    "low": prices * 0.999,
                    "close": prices,
                    "adj_close": prices,
                    "volume": 1_000_000,
                }
            )
        )
    long_df = pd.concat(frames, ignore_index=True)

    class _FakeSource:
        name = "api_test_fake_source"

        def fetch(self, symbols, start, end, interval="1d"):
            start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
            mask = long_df["symbol"].isin(symbols) & (long_df["date"] >= start_ts) & (long_df["date"] <= end_ts)
            sliced = long_df.loc[mask].copy()
            sliced["source"] = self.name
            return sliced.sort_values(["symbol", "date"]).reset_index(drop=True)

    class _BrokenSource:
        name = "api_test_broken_source"

        def fetch(self, symbols, start, end, interval="1d"):
            raise DataSourceError("simulated vendor outage")

    if "api_test_fake_source" not in DATA_SOURCE_REGISTRY:
        DATA_SOURCE_REGISTRY.register("api_test_fake_source")(_FakeSource)
    if "api_test_broken_source" not in DATA_SOURCE_REGISTRY:
        DATA_SOURCE_REGISTRY.register("api_test_broken_source")(_BrokenSource)
    yield
    DATA_SOURCE_REGISTRY._items.pop("api_test_fake_source", None)
    DATA_SOURCE_REGISTRY._items.pop("api_test_broken_source", None)


@pytest.fixture
def auth_headers(client):
    client.post("/auth/register", json={"email": "run@example.com", "password": "password123"})
    resp = client.post("/auth/login", data={"username": "run@example.com", "password": "password123"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_run_backtest_succeeds_offline(client, auth_headers) -> None:
    resp = client.post(
        "/runs", json={"kind": "backtest", "config_json": SYNTHETIC_CONFIG_TEMPLATE}, headers=auth_headers
    )
    assert resp.status_code == 201
    run_id = resp.json()["id"]

    # task_always_eager=True -> already finished by the time .delay() returns
    resp = client.get(f"/runs/{run_id}", headers=auth_headers)
    body = resp.json()
    assert body["status"] == "success", body
    assert "sharpe" in body["result_json"]["metrics"]
    assert len(body["result_json"]["equity_curve"]) > 0


def test_run_research_kind_has_no_backtest_metrics(client, auth_headers) -> None:
    resp = client.post(
        "/runs", json={"kind": "research", "config_json": SYNTHETIC_CONFIG_TEMPLATE}, headers=auth_headers
    )
    run_id = resp.json()["id"]

    resp = client.get(f"/runs/{run_id}", headers=auth_headers)
    body = resp.json()
    assert body["status"] == "success"
    assert "ic_summary" in body["result_json"]
    assert "metrics" not in body["result_json"]


def test_run_with_failing_source_reports_error(client, auth_headers) -> None:
    bad_config = {
        **SYNTHETIC_CONFIG_TEMPLATE,
        "universe": {**SYNTHETIC_CONFIG_TEMPLATE["universe"], "primary_source": "api_test_broken_source"},
    }
    resp = client.post("/runs", json={"kind": "backtest", "config_json": bad_config}, headers=auth_headers)
    run_id = resp.json()["id"]

    resp = client.get(f"/runs/{run_id}", headers=auth_headers)
    body = resp.json()
    assert body["status"] == "failed"
    assert "simulated vendor outage" in body["error_message"]


def test_run_requires_config_id_or_json(client, auth_headers) -> None:
    resp = client.post("/runs", json={"kind": "backtest"}, headers=auth_headers)
    assert resp.status_code == 400


def test_run_from_saved_config(client, auth_headers) -> None:
    resp = client.post(
        "/configs", json={"name": "saved", "config_json": SYNTHETIC_CONFIG_TEMPLATE}, headers=auth_headers
    )
    config_id = resp.json()["id"]

    resp = client.post("/runs", json={"kind": "backtest", "config_id": config_id}, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["config_id"] == config_id


def test_run_with_unknown_config_id_rejected(client, auth_headers) -> None:
    resp = client.post("/runs", json={"kind": "backtest", "config_id": 99999}, headers=auth_headers)
    assert resp.status_code == 404


def test_runs_scoped_to_owner(client, auth_headers) -> None:
    client.post("/runs", json={"kind": "research", "config_json": SYNTHETIC_CONFIG_TEMPLATE}, headers=auth_headers)

    client.post("/auth/register", json={"email": "other@example.com", "password": "password123"})
    other_token = client.post(
        "/auth/login", data={"username": "other@example.com", "password": "password123"}
    ).json()["access_token"]

    resp = client.get("/runs", headers={"Authorization": f"Bearer {other_token}"})
    assert resp.json() == []

    resp = client.get("/runs", headers=auth_headers)
    assert len(resp.json()) == 1


def test_artifact_serving_and_ownership(client, auth_headers) -> None:
    resp = client.post(
        "/runs", json={"kind": "backtest", "config_json": SYNTHETIC_CONFIG_TEMPLATE}, headers=auth_headers
    )
    run_id = resp.json()["id"]

    resp = client.get(f"/runs/{run_id}/artifacts/tearsheet.md", headers=auth_headers)
    assert resp.status_code == 200
    assert b"Backtest Metrics" in resp.content

    resp = client.get(f"/runs/{run_id}/artifacts/does-not-exist.png", headers=auth_headers)
    assert resp.status_code == 404

    client.post("/auth/register", json={"email": "intruder2@example.com", "password": "password123"})
    intruder_token = client.post(
        "/auth/login", data={"username": "intruder2@example.com", "password": "password123"}
    ).json()["access_token"]
    resp = client.get(
        f"/runs/{run_id}/artifacts/tearsheet.md", headers={"Authorization": f"Bearer {intruder_token}"}
    )
    assert resp.status_code == 404


def test_research_run_has_no_artifacts(client, auth_headers) -> None:
    resp = client.post(
        "/runs", json={"kind": "research", "config_json": SYNTHETIC_CONFIG_TEMPLATE}, headers=auth_headers
    )
    run_id = resp.json()["id"]
    resp = client.get(f"/runs/{run_id}/artifacts/tearsheet.md", headers=auth_headers)
    assert resp.status_code == 404
