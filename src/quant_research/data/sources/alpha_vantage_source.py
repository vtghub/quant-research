from __future__ import annotations

import os
from datetime import date
from typing import Sequence

import pandas as pd
import requests

from quant_research.core.exceptions import DataSourceError
from quant_research.core.registries import DATA_SOURCE_REGISTRY
from quant_research.data.base import OHLCVDataSource, normalize_ohlcv

BASE_URL = "https://www.alphavantage.co/query"


@DATA_SOURCE_REGISTRY.register("alpha_vantage")
class AlphaVantageSource(OHLCVDataSource):
    """Free-tier equity/ETF OHLCV via Alpha Vantage's TIME_SERIES_DAILY endpoint.
    Requires a free API key (https://www.alphavantage.co/support/#api-key) passed
    explicitly or via ALPHAVANTAGE_API_KEY. Two important free-tier limits: (1)
    ~25 requests/day, so this is best used sparingly as a spot cross-check, not a
    primary bulk source -- the cache is what makes that survivable; (2) the free
    tier's daily endpoint is *unadjusted* (dividend/split-adjusted data moved
    behind Alpha Vantage's premium tier), so adj_close here is just an alias for
    close -- do not treat it as comparable to yfinance's true adj_close."""

    name = "alpha_vantage"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("ALPHAVANTAGE_API_KEY")

    def fetch(self, symbols: Sequence[str], start: date, end: date, interval: str = "1d") -> pd.DataFrame:
        frames = [self._fetch_one(symbol, start, end) for symbol in symbols]
        combined = pd.concat(frames, ignore_index=True)
        return normalize_ohlcv(combined, self.name)

    def _fetch_one(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        if not self.api_key:
            raise DataSourceError(
                "ALPHAVANTAGE_API_KEY not set. Get a free key at "
                "https://www.alphavantage.co/support/#api-key and set it, or pass api_key=."
            )

        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": "full",
            "apikey": self.api_key,
        }
        try:
            response = requests.get(BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise DataSourceError(f"alpha_vantage fetch failed for {symbol}: {exc}") from exc

        if "Note" in payload or "Information" in payload:
            # rate-limit / free-tier notice; Alpha Vantage returns HTTP 200 for these
            raise DataSourceError(
                f"alpha_vantage rate-limited or rejected request for {symbol}: "
                f"{payload.get('Note') or payload.get('Information')}"
            )

        series = payload.get("Time Series (Daily)")
        if not series:
            raise DataSourceError(f"alpha_vantage returned no data for {symbol}: {payload.get('Error Message', payload)}")

        start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
        rows = []
        for date_str, fields in series.items():
            ts = pd.Timestamp(date_str)
            if start_ts <= ts <= end_ts:
                rows.append(
                    {
                        "date": ts,
                        "symbol": symbol,
                        "open": float(fields["1. open"]),
                        "high": float(fields["2. high"]),
                        "low": float(fields["3. low"]),
                        "close": float(fields["4. close"]),
                        "adj_close": float(fields["4. close"]),  # no adjusted series on the free tier
                        "volume": float(fields["5. volume"]),
                    }
                )

        if not rows:
            raise DataSourceError(f"alpha_vantage returned no data for {symbol} in [{start}..{end}]")
        return pd.DataFrame(rows)
