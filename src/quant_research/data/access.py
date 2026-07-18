from __future__ import annotations

from datetime import date
from typing import Sequence

import pandas as pd

from quant_research.cache.base import CacheBackend, CacheKey
from quant_research.core.hooks import HookEvent, HookManager
from quant_research.data.base import OHLCVDataSource


class DataAccessLayer:
    """Fetch-through cache: reuses cached rows when the requested range is already
    covered, and otherwise fetches only the union of the cached and requested
    ranges before overwriting the cache entry (never re-fetches data it already has
    for a strictly narrower request)."""

    def __init__(self, cache: CacheBackend, hooks: HookManager | None = None) -> None:
        self.cache = cache
        self.hooks = hooks or HookManager()

    def get_ohlcv_long(
        self,
        source: OHLCVDataSource,
        symbols: Sequence[str],
        start: date,
        end: date,
        interval: str = "1d",
        adjusted: bool = True,
    ) -> pd.DataFrame:
        frames = [self._get_one(source, symbol, start, end, interval, adjusted) for symbol in symbols]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def _get_one(
        self,
        source: OHLCVDataSource,
        symbol: str,
        start: date,
        end: date,
        interval: str,
        adjusted: bool,
    ) -> pd.DataFrame:
        key = CacheKey(source=source.name, symbol=symbol, interval=interval, adjusted=adjusted)
        start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
        cached = self.cache.get(key)

        if cached is not None and not cached.empty:
            covers = cached["date"].min() <= start_ts and cached["date"].max() >= end_ts
            if covers:
                return self._slice(cached, start_ts, end_ts)
            fetch_start = min(cached["date"].min(), start_ts).date()
            fetch_end = max(cached["date"].max(), end_ts).date()
        else:
            fetch_start, fetch_end = start, end

        self.hooks.fire(HookEvent.BEFORE_FETCH, source=source.name, symbol=symbol, start=fetch_start, end=fetch_end)
        fetched = source.fetch([symbol], fetch_start, fetch_end, interval)
        self.hooks.fire(HookEvent.AFTER_FETCH, source=source.name, symbol=symbol, df=fetched)

        self.cache.put(key, fetched)
        return self._slice(fetched, start_ts, end_ts)

    @staticmethod
    def _slice(df: pd.DataFrame, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> pd.DataFrame:
        mask = (df["date"] >= start_ts) & (df["date"] <= end_ts)
        return df.loc[mask].reset_index(drop=True)

    @staticmethod
    def to_wide(long_df: pd.DataFrame, price_field: str = "adj_close") -> pd.DataFrame:
        if long_df.empty:
            return pd.DataFrame()
        wide = long_df.pivot(index="date", columns="symbol", values=price_field)
        wide.index = pd.to_datetime(wide.index)
        return wide.sort_index()

    @staticmethod
    def broadcast_macro(
        macro_long_df: pd.DataFrame,
        series_id: str,
        calendar_index: pd.DatetimeIndex,
        symbols: Sequence[str],
    ) -> pd.DataFrame:
        """Reindex a single macro series onto the (equity/ETF) trading calendar with
        forward-fill (macro releases are far lower frequency than daily bars), and
        broadcast the resulting value across every symbol column -- the shape
        signals expect. This is the MVP calendar-alignment simplification: no
        attempt is made to model 24/7 vs exchange-calendar timing precisely."""
        series = macro_long_df.loc[macro_long_df["series_id"] == series_id].set_index("date")["value"]
        series = series.sort_index()
        aligned = series.reindex(calendar_index, method="ffill")
        return pd.DataFrame({symbol: aligned for symbol in symbols}, index=calendar_index)

    @staticmethod
    def fundamentals_to_wide(
        fundamentals_long_df: pd.DataFrame,
        concept: str,
        calendar_index: pd.DatetimeIndex,
        symbols: Sequence[str],
    ) -> pd.DataFrame:
        """Pivot one fundamentals concept (e.g. 'EarningsPerShareBasic') to a wide
        date x symbol frame -- the same shape a price panel has -- reindexed onto
        the trading calendar with forward-fill (filings are quarterly at best, far
        lower frequency than daily bars) and missing symbols filled with NaN so
        the frame always has every universe column, consistent with how
        Signal.compute treats warm-up NaN as "no data yet", not an error."""
        subset = fundamentals_long_df.loc[fundamentals_long_df["concept"] == concept]
        wide = subset.pivot_table(index="date", columns="symbol", values="value", aggfunc="last")
        wide = wide.reindex(columns=symbols)
        wide.index = pd.to_datetime(wide.index)
        wide = wide.sort_index().reindex(calendar_index, method="ffill")
        return wide
