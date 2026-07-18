from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class CacheKey:
    source: str
    symbol: str
    interval: str
    adjusted: bool = True

    def relative_path(self) -> Path:
        return Path(self.source) / self.interval / ("adj" if self.adjusted else "raw") / f"{self.symbol}.parquet"


class CacheBackend(ABC):
    @abstractmethod
    def get(self, key: CacheKey) -> pd.DataFrame | None:
        """Return the cached long-format frame for this key, or None if absent."""

    @abstractmethod
    def put(self, key: CacheKey, df: pd.DataFrame) -> None:
        """Persist (overwrite) the frame for this key."""

    @abstractmethod
    def exists(self, key: CacheKey) -> bool: ...

    @abstractmethod
    def invalidate(self, key: CacheKey) -> None:
        """Remove any cached entry for this key. No-op if absent."""

    @abstractmethod
    def fetched_at(self, key: CacheKey) -> pd.Timestamp | None:
        """When this entry was last written, or None if absent."""
