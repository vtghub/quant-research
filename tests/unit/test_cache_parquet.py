from __future__ import annotations

import pandas as pd
import pytest

from quant_research.cache.base import CacheKey
from quant_research.cache.parquet_backend import ParquetCacheBackend
from quant_research.core.registries import CACHE_BACKEND_REGISTRY

# Generic get/put/invalidate/fetched_at correctness is covered once, for every
# backend, in test_cache_backend_contract.py. This file only covers
# parquet-specific concerns (registration, on-disk layout).


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


def test_put_writes_one_parquet_file_per_key(backend: ParquetCacheBackend, tmp_path, sample_df: pd.DataFrame) -> None:
    key = CacheKey(source="yfinance", symbol="AAA", interval="1d")
    backend.put(key, sample_df)

    data_path, meta_path = backend._paths(key)
    assert data_path.exists()
    assert data_path.suffix == ".parquet"
    assert meta_path.exists()
    assert meta_path.name.endswith(".meta.json")
