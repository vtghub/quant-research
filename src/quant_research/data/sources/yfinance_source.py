from __future__ import annotations

from datetime import date
from typing import Sequence

import pandas as pd
import yfinance as yf

from quant_research.core.exceptions import DataSourceError
from quant_research.core.registries import DATA_SOURCE_REGISTRY
from quant_research.data.base import OHLCVDataSource, normalize_ohlcv


@DATA_SOURCE_REGISTRY.register("yfinance")
class YFinanceSource(OHLCVDataSource):
    """Equities, ETFs, FX pairs, and crypto (e.g. BTC-USD) all share this one
    vendor and schema -- yfinance is the primary source for all three asset
    classes in the multi-asset universe, not just equities."""

    name = "yfinance"

    def fetch(self, symbols: Sequence[str], start: date, end: date, interval: str = "1d") -> pd.DataFrame:
        frames = [self._fetch_one(symbol, start, end, interval) for symbol in symbols]
        combined = pd.concat(frames, ignore_index=True)
        return normalize_ohlcv(combined, self.name)

    def _fetch_one(self, symbol: str, start: date, end: date, interval: str) -> pd.DataFrame:
        try:
            raw = yf.Ticker(symbol).history(start=start, end=end, interval=interval, auto_adjust=False)
        except Exception as exc:
            raise DataSourceError(f"yfinance fetch failed for {symbol}: {exc}") from exc

        if raw is None or raw.empty:
            raise DataSourceError(f"yfinance returned no data for {symbol} [{start}..{end}]")

        raw = raw.reset_index()
        date_col = "Date" if "Date" in raw.columns else "Datetime"
        adj_close = raw["Adj Close"] if "Adj Close" in raw.columns else raw["Close"]
        return pd.DataFrame(
            {
                "date": raw[date_col],
                "symbol": symbol,
                "open": raw["Open"],
                "high": raw["High"],
                "low": raw["Low"],
                "close": raw["Close"],
                "adj_close": adj_close,
                "volume": raw["Volume"],
            }
        )
