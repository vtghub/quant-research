from __future__ import annotations


def test_registry_lists_builtins(client) -> None:
    resp = client.get("/registry")
    assert resp.status_code == 200
    data = resp.json()
    assert "yfinance" in data["data_sources"]
    assert "sec_edgar" in data["fundamentals_sources"]
    assert "fred" in data["macro_sources"]
    assert {"parquet", "duckdb"} <= set(data["cache_backends"])
    assert {"static", "point_in_time"} <= set(data["universe_providers"])
    assert "momentum" in data["signals"]
    assert "composite" in data["signals"]
    assert "rank_weighted_long_short" in data["strategies"]
