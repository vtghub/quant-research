from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from quant_research.cache.base import CacheBackend, CacheKey
from quant_research.core.exceptions import CacheError
from quant_research.core.registries import CACHE_BACKEND_REGISTRY

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS cache_entries (
    source VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,
    interval VARCHAR NOT NULL,
    adjusted BOOLEAN NOT NULL,
    fetched_at TIMESTAMP NOT NULL,
    min_date TIMESTAMP,
    max_date TIMESTAMP,
    rows BIGINT NOT NULL,
    payload BLOB NOT NULL,
    PRIMARY KEY (source, symbol, interval, adjusted)
)
"""


@CACHE_BACKEND_REGISTRY.register("duckdb")
class DuckDBCacheBackend(CacheBackend):
    """Single-file embedded DuckDB database: one row per cache key, the frame
    itself stored as an in-memory parquet blob (so, unlike a fixed OHLCV table,
    this works for any long-format frame the same way ParquetCacheBackend does).
    A drop-in swap behind the same CacheBackend interface -- useful once you want
    every cached symbol queryable via SQL from one file instead of scattered
    across many small parquet files. `duckdb` is an optional extra
    (`pip install 'quant-research[duckdb]'`); its absence never breaks the base
    install, only this backend's use."""

    def __init__(self, root_dir: str | Path = ".cache/quant_research", db_filename: str = "cache.duckdb") -> None:
        try:
            import duckdb
        except ImportError as exc:
            raise CacheError("duckdb is not installed; run `pip install 'quant-research[duckdb]'`") from exc

        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root_dir / db_filename
        self._conn = duckdb.connect(str(self.db_path))
        self._conn.execute(_CREATE_TABLE_SQL)

    def close(self) -> None:
        self._conn.close()

    def _fetch_row(self, key: CacheKey):
        return self._conn.execute(
            "SELECT fetched_at, payload FROM cache_entries "
            "WHERE source=? AND symbol=? AND interval=? AND adjusted=?",
            [key.source, key.symbol, key.interval, key.adjusted],
        ).fetchone()

    def exists(self, key: CacheKey) -> bool:
        return self._fetch_row(key) is not None

    def get(self, key: CacheKey) -> pd.DataFrame | None:
        row = self._fetch_row(key)
        if row is None:
            return None
        _, payload = row
        try:
            df = pd.read_parquet(io.BytesIO(payload))
        except Exception as exc:  # pragma: no cover - corrupted cache is rare
            raise CacheError(f"failed reading duckdb cache entry {key}: {exc}") from exc
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        return df

    def put(self, key: CacheKey, df: pd.DataFrame) -> None:
        buffer = io.BytesIO()
        try:
            df.to_parquet(buffer, index=False)
        except Exception as exc:
            raise CacheError(f"failed writing duckdb cache entry {key}: {exc}") from exc
        payload = buffer.getvalue()

        dates = pd.to_datetime(df["date"]) if "date" in df.columns and len(df) else pd.Series(dtype="datetime64[ns]")
        fetched_at = pd.Timestamp.now(tz="UTC").tz_localize(None)
        min_date = dates.min() if len(dates) else None
        max_date = dates.max() if len(dates) else None

        self._conn.execute(
            "DELETE FROM cache_entries WHERE source=? AND symbol=? AND interval=? AND adjusted=?",
            [key.source, key.symbol, key.interval, key.adjusted],
        )
        self._conn.execute(
            "INSERT INTO cache_entries "
            "(source, symbol, interval, adjusted, fetched_at, min_date, max_date, rows, payload) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [key.source, key.symbol, key.interval, key.adjusted, fetched_at, min_date, max_date, len(df), payload],
        )

    def invalidate(self, key: CacheKey) -> None:
        self._conn.execute(
            "DELETE FROM cache_entries WHERE source=? AND symbol=? AND interval=? AND adjusted=?",
            [key.source, key.symbol, key.interval, key.adjusted],
        )

    def fetched_at(self, key: CacheKey) -> pd.Timestamp | None:
        row = self._fetch_row(key)
        if row is None:
            return None
        fetched_at, _ = row
        return pd.Timestamp(fetched_at) if fetched_at is not None else None
