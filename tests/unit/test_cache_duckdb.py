from __future__ import annotations

import pandas as pd
import pytest

from quant_research.cache.base import CacheKey
from quant_research.cache.duckdb_backend import DuckDBCacheBackend
from quant_research.core.registries import CACHE_BACKEND_REGISTRY

# Generic get/put/invalidate/fetched_at correctness is covered once, for every
# backend, in test_cache_backend_contract.py. This file only covers
# duckdb-specific concerns (registration, single-file storage, SQL queryability).


@pytest.fixture
def sample_df() -> pd.DataFrame:
    dates = pd.bdate_range("2022-01-01", periods=5)
    return pd.DataFrame(
        {
            "date": dates,
            "symbol": "AAA",
            "close": [1.0, 2.0, 3.0, 4.0, 5.0],
            "adj_close": [1.0, 2.0, 3.0, 4.0, 5.0],
        }
    )


def test_duckdb_backend_is_registered() -> None:
    assert "duckdb" in CACHE_BACKEND_REGISTRY
    assert CACHE_BACKEND_REGISTRY.get("duckdb") is DuckDBCacheBackend


def test_everything_lives_in_one_db_file(tmp_path, sample_df: pd.DataFrame) -> None:
    backend = DuckDBCacheBackend(root_dir=tmp_path)
    try:
        backend.put(CacheKey(source="yfinance", symbol="AAA", interval="1d"), sample_df)
        backend.put(CacheKey(source="yfinance", symbol="BBB", interval="1d"), sample_df)
        backend.put(CacheKey(source="stooq", symbol="AAA", interval="1d"), sample_df)

        db_files = list(tmp_path.glob("*.duckdb"))
        assert len(db_files) == 1  # unlike parquet (one file per key), everything is one file
    finally:
        backend.close()


def test_reopening_the_same_db_file_sees_prior_entries(tmp_path, sample_df: pd.DataFrame) -> None:
    key = CacheKey(source="yfinance", symbol="AAA", interval="1d")

    first = DuckDBCacheBackend(root_dir=tmp_path)
    first.put(key, sample_df)
    first.close()

    second = DuckDBCacheBackend(root_dir=tmp_path)
    try:
        assert second.exists(key)
        result = second.get(key)
        assert len(result) == len(sample_df)
    finally:
        second.close()


def test_entries_are_queryable_via_sql(tmp_path, sample_df: pd.DataFrame) -> None:
    backend = DuckDBCacheBackend(root_dir=tmp_path)
    try:
        backend.put(CacheKey(source="yfinance", symbol="AAA", interval="1d"), sample_df)
        backend.put(CacheKey(source="yfinance", symbol="BBB", interval="1d"), sample_df)

        rows = backend._conn.execute(
            "SELECT symbol, rows FROM cache_entries WHERE source = 'yfinance' ORDER BY symbol"
        ).fetchall()
        assert rows == [("AAA", 5), ("BBB", 5)]
    finally:
        backend.close()


def test_missing_duckdb_dependency_raises_cache_error(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    import sys

    from quant_research.core.exceptions import CacheError

    monkeypatch.setitem(sys.modules, "duckdb", None)
    with pytest.raises(CacheError, match="duckdb is not installed"):
        DuckDBCacheBackend(root_dir=tmp_path)
