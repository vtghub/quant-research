from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import ClassVar, Sequence

import pandas as pd

OHLCV_COLUMNS = ["date", "symbol", "open", "high", "low", "close", "adj_close", "volume", "source"]
MACRO_COLUMNS = ["date", "series_id", "value", "source"]
FUNDAMENTALS_COLUMNS = ["date", "symbol", "concept", "value", "source"]


def normalize_ohlcv(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Coerce a source-specific frame into the canonical schema: tz-naive midnight
    dates, sorted by (symbol, date), exactly OHLCV_COLUMNS in order."""
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.tz_localize(None).dt.normalize()
    out["source"] = source
    missing = set(OHLCV_COLUMNS) - set(out.columns)
    if missing:
        raise ValueError(f"normalize_ohlcv: missing columns {sorted(missing)}")
    out = out[OHLCV_COLUMNS].sort_values(["symbol", "date"]).reset_index(drop=True)
    return out


def normalize_macro(df: pd.DataFrame, source: str) -> pd.DataFrame:
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.tz_localize(None).dt.normalize()
    out["source"] = source
    missing = set(MACRO_COLUMNS) - set(out.columns)
    if missing:
        raise ValueError(f"normalize_macro: missing columns {sorted(missing)}")
    out = out[MACRO_COLUMNS].sort_values(["series_id", "date"]).reset_index(drop=True)
    return out


def normalize_fundamentals(df: pd.DataFrame, source: str) -> pd.DataFrame:
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.tz_localize(None).dt.normalize()
    out["source"] = source
    missing = set(FUNDAMENTALS_COLUMNS) - set(out.columns)
    if missing:
        raise ValueError(f"normalize_fundamentals: missing columns {sorted(missing)}")
    out = out[FUNDAMENTALS_COLUMNS].sort_values(["symbol", "concept", "date"]).reset_index(drop=True)
    return out


class OHLCVDataSource(ABC):
    name: ClassVar[str]

    @abstractmethod
    def fetch(self, symbols: Sequence[str], start: date, end: date, interval: str = "1d") -> pd.DataFrame:
        """Return long-format OHLCV_COLUMNS data for the requested symbols/range.

        Must raise DataSourceError (not a vendor-specific exception) on failure, and
        must never silently return an empty frame for a symbol that genuinely errored.
        """


class MacroDataSource(ABC):
    name: ClassVar[str]

    @abstractmethod
    def fetch(self, series_ids: Sequence[str], start: date, end: date) -> pd.DataFrame:
        """Return long-format MACRO_COLUMNS data for the requested series/range."""


class FundamentalsDataSource(ABC):
    name: ClassVar[str]

    @abstractmethod
    def fetch(self, symbols: Sequence[str], concepts: Sequence[str], start: date, end: date) -> pd.DataFrame:
        """Return long-format FUNDAMENTALS_COLUMNS data (one row per symbol x
        concept x filing/period-end date) for the requested symbols/concepts/range."""
