from __future__ import annotations

import pandas as pd
import pytest

from quant_research.cache.base import CacheKey
from quant_research.cache.duckdb_backend import DuckDBCacheBackend
from quant_research.cache.parquet_backend import ParquetCacheBackend

BACKEND_FACTORIES = [ParquetCacheBackend, DuckDBCacheBackend]


@pytest.fixture(params=BACKEND_FACTORIES, ids=["parquet", "duckdb"])
def backend(request, tmp_path):
    """Every CacheBackend implementation must satisfy this same contract --
    parametrized so a new backend only needs to be added to BACKEND_FACTORIES."""
    instance = request.param(root_dir=tmp_path)
    yield instance
    close = getattr(instance, "close", None)
    if close is not None:
        close()


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


def test_get_missing_key_returns_none(backend) -> None:
    key = CacheKey(source="yfinance", symbol="AAA", interval="1d")
    assert backend.get(key) is None
    assert not backend.exists(key)
    assert backend.fetched_at(key) is None


def test_put_then_get_roundtrip(backend, sample_df: pd.DataFrame) -> None:
    key = CacheKey(source="yfinance", symbol="AAA", interval="1d")
    backend.put(key, sample_df)

    assert backend.exists(key)
    result = backend.get(key)
    assert result is not None
    pd.testing.assert_series_equal(
        result["close"].reset_index(drop=True), sample_df["close"].reset_index(drop=True), check_dtype=False
    )
    assert backend.fetched_at(key) is not None


def test_put_overwrites_previous_entry(backend, sample_df: pd.DataFrame) -> None:
    key = CacheKey(source="yfinance", symbol="AAA", interval="1d")
    backend.put(key, sample_df)
    backend.put(key, sample_df.iloc[:2])

    result = backend.get(key)
    assert len(result) == 2


def test_invalidate_removes_entry(backend, sample_df: pd.DataFrame) -> None:
    key = CacheKey(source="yfinance", symbol="AAA", interval="1d")
    backend.put(key, sample_df)
    backend.invalidate(key)

    assert not backend.exists(key)
    assert backend.get(key) is None


def test_invalidate_missing_key_is_noop(backend) -> None:
    key = CacheKey(source="yfinance", symbol="ZZZ", interval="1d")
    backend.invalidate(key)  # should not raise


def test_distinct_keys_dont_collide(backend, sample_df: pd.DataFrame) -> None:
    raw_key = CacheKey(source="yfinance", symbol="AAA", interval="1d", adjusted=False)
    adj_key = CacheKey(source="yfinance", symbol="AAA", interval="1d", adjusted=True)
    other_symbol_key = CacheKey(source="yfinance", symbol="BBB", interval="1d", adjusted=False)

    backend.put(raw_key, sample_df)

    assert not backend.exists(adj_key)
    assert not backend.exists(other_symbol_key)
