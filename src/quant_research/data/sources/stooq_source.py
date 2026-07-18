from __future__ import annotations

import io
from datetime import date
from typing import Sequence

import pandas as pd
import requests

from quant_research.core.exceptions import DataSourceError
from quant_research.core.registries import DATA_SOURCE_REGISTRY
from quant_research.data.base import OHLCVDataSource, normalize_ohlcv

STOOQ_URL = "https://stooq.com/q/d/l/"


def _to_stooq_symbol(symbol: str) -> str:
    """Stooq's US-listed-ticker convention: plain tickers need a '.us' suffix
    (e.g. SPY -> spy.us); symbols that already carry a market suffix (a '.') are
    passed through unchanged. This is the one place this vendor quirk lives."""
    lowered = symbol.lower()
    return lowered if "." in lowered else f"{lowered}.us"


@DATA_SOURCE_REGISTRY.register("stooq")
class StooqSource(OHLCVDataSource):
    """Free, no-key equity/ETF data. Treat as a cross-check/fallback source only --
    Stooq's dividend-adjustment methodology is not guaranteed to match yfinance's
    adj_close, so it is not a silent drop-in replacement (see README caveats)."""

    name = "stooq"

    def fetch(self, symbols: Sequence[str], start: date, end: date, interval: str = "1d") -> pd.DataFrame:
        frames = [self._fetch_one(symbol, start, end) for symbol in symbols]
        combined = pd.concat(frames, ignore_index=True)
        return normalize_ohlcv(combined, self.name)

    def _fetch_one(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        params = {
            "s": _to_stooq_symbol(symbol),
            "d1": pd.Timestamp(start).strftime("%Y%m%d"),
            "d2": pd.Timestamp(end).strftime("%Y%m%d"),
            "i": "d",
        }
        try:
            response = requests.get(STOOQ_URL, params=params, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise DataSourceError(f"stooq fetch failed for {symbol}: {exc}") from exc

        text = response.text.strip()
        if not text or text.lower().startswith("no data"):
            raise DataSourceError(f"stooq returned no data for {symbol} [{start}..{end}]")

        try:
            raw = pd.read_csv(io.StringIO(text))
        except Exception as exc:
            raise DataSourceError(f"stooq returned unparsable data for {symbol}: {exc}") from exc

        required = {"Date", "Open", "High", "Low", "Close", "Volume"}
        if raw.empty or not required.issubset(raw.columns):
            raise DataSourceError(f"stooq returned no data for {symbol} [{start}..{end}]")

        return pd.DataFrame(
            {
                "date": raw["Date"],
                "symbol": symbol,
                "open": raw["Open"],
                "high": raw["High"],
                "low": raw["Low"],
                "close": raw["Close"],
                "adj_close": raw["Close"],  # Stooq has no separate dividend-adjusted series
                "volume": raw["Volume"],
            }
        )
