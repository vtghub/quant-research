from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from quant_research.cache.base import CacheBackend, CacheKey
from quant_research.core.exceptions import CacheError
from quant_research.core.registries import CACHE_BACKEND_REGISTRY


@CACHE_BACKEND_REGISTRY.register("parquet")
class ParquetCacheBackend(CacheBackend):
    """One parquet file + a JSON metadata sidecar per cache key."""

    def __init__(self, root_dir: str | Path = ".cache/quant_research") -> None:
        self.root_dir = Path(root_dir)

    def _paths(self, key: CacheKey) -> tuple[Path, Path]:
        data_path = self.root_dir / key.relative_path()
        meta_path = data_path.with_suffix(".meta.json")
        return data_path, meta_path

    def exists(self, key: CacheKey) -> bool:
        data_path, _ = self._paths(key)
        return data_path.exists()

    def get(self, key: CacheKey) -> pd.DataFrame | None:
        data_path, _ = self._paths(key)
        if not data_path.exists():
            return None
        try:
            df = pd.read_parquet(data_path)
        except Exception as exc:  # pragma: no cover - corrupted cache is rare
            raise CacheError(f"failed reading cache entry {data_path}: {exc}") from exc
        df["date"] = pd.to_datetime(df["date"])
        return df

    def put(self, key: CacheKey, df: pd.DataFrame) -> None:
        data_path, meta_path = self._paths(key)
        data_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            df.to_parquet(data_path, index=False)
        except Exception as exc:
            raise CacheError(f"failed writing cache entry {data_path}: {exc}") from exc
        dates = pd.to_datetime(df["date"]) if "date" in df.columns and len(df) else pd.Series(dtype="datetime64[ns]")
        meta = {
            "fetched_at": pd.Timestamp.now(tz="UTC").isoformat(),
            "min_date": dates.min().isoformat() if len(dates) else None,
            "max_date": dates.max().isoformat() if len(dates) else None,
            "rows": len(df),
        }
        meta_path.write_text(json.dumps(meta, indent=2))

    def invalidate(self, key: CacheKey) -> None:
        data_path, meta_path = self._paths(key)
        data_path.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)

    def fetched_at(self, key: CacheKey) -> pd.Timestamp | None:
        _, meta_path = self._paths(key)
        if not meta_path.exists():
            return None
        meta = json.loads(meta_path.read_text())
        fetched = meta.get("fetched_at")
        return pd.Timestamp(fetched) if fetched else None
