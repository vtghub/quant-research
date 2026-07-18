from __future__ import annotations

import pandas as pd
import pytest

from quant_research.cache.base import CacheKey
from quant_research.cache.parquet_backend import ParquetCacheBackend
from quant_research.core.registries import CACHE_BACKEND_REGISTRY


@pytest.fixture
def backend(tmp_path) -> ParquetCacheBackend:
    return ParquetCacheBackend(root_dir=tmp_path)


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


def test_parquet_backend_is_registered() -> None:
    assert "parquet" in CACHE_BACKEND_REGISTRY
    assert CACHE_BACKEND_REGISTRY.get("parquet") is ParquetCacheBackend


def test_get_missing_key_returns_none(backend: ParquetCacheBackend) -> None:
    key = CacheKey(source="yfinance", symbol="AAA", interval="1d")
    assert backend.get(key) is None
    assert not backend.exists(key)
    assert backend.fetched_at(key) is None


def test_put_then_get_roundtrip(backend: ParquetCacheBackend, sample_df: pd.DataFrame) -> None:
    key = CacheKey(source="yfinance", symbol="AAA", interval="1d")
    backend.put(key, sample_df)

    assert backend.exists(key)
    result = backend.get(key)
    assert result is not None
    pd.testing.assert_series_equal(result["close"], sample_df["close"], check_dtype=False)
    assert backend.fetched_at(key) is not None


def test_put_overwrites_previous_entry(backend: ParquetCacheBackend, sample_df: pd.DataFrame) -> None:
    key = CacheKey(source="yfinance", symbol="AAA", interval="1d")
    backend.put(key, sample_df)
    smaller = sample_df.iloc[:2]
    backend.put(key, smaller)
    result = backend.get(key)
    assert len(result) == 2


def test_invalidate_removes_entry(backend: ParquetCacheBackend, sample_df: pd.DataFrame) -> None:
    key = CacheKey(source="yfinance", symbol="AAA", interval="1d")
    backend.put(key, sample_df)
    backend.invalidate(key)
    assert not backend.exists(key)
    assert backend.get(key) is None


def test_invalidate_missing_key_is_noop(backend: ParquetCacheBackend) -> None:
    key = CacheKey(source="yfinance", symbol="ZZZ", interval="1d")
    backend.invalidate(key)  # should not raise


def test_different_symbols_and_adjustment_get_distinct_paths(
    backend: ParquetCacheBackend, sample_df: pd.DataFrame
) -> None:
    raw_key = CacheKey(source="yfinance", symbol="AAA", interval="1d", adjusted=False)
    adj_key = CacheKey(source="yfinance", symbol="AAA", interval="1d", adjusted=True)
    backend.put(raw_key, sample_df)
    assert not backend.exists(adj_key)
