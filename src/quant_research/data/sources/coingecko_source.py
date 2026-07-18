from __future__ import annotations

import re
from datetime import date
from typing import Sequence

import pandas as pd
import requests

from quant_research.core.exceptions import DataSourceError
from quant_research.core.registries import DATA_SOURCE_REGISTRY
from quant_research.data.base import OHLCVDataSource, normalize_ohlcv

BASE_URL = "https://api.coingecko.com/api/v3"

# CoinGecko addresses coins by an id, not a ticker -- this map is the one place
# that symbol->id translation lives. Extend it to support more coins.
_SYMBOL_TO_COINGECKO_ID = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "XRP": "ripple",
    "LTC": "litecoin",
    "DOT": "polkadot",
    "MATIC": "matic-network",
    "AVAX": "avalanche-2",
    "BNB": "binancecoin",
}

_QUOTE_SUFFIX_RE = re.compile(r"-?(USD|USDT|USDC)$", re.IGNORECASE)


def _to_coingecko_id(symbol: str) -> str:
    base = _QUOTE_SUFFIX_RE.sub("", symbol.upper())
    try:
        return _SYMBOL_TO_COINGECKO_ID[base]
    except KeyError:
        raise DataSourceError(
            f"no CoinGecko id mapping for '{symbol}' (base '{base}'). "
            f"Add it to _SYMBOL_TO_COINGECKO_ID in coingecko_source.py."
        ) from None


@DATA_SOURCE_REGISTRY.register("coingecko")
class CoinGeckoSource(OHLCVDataSource):
    """Free, no-key crypto data -- a second vendor for the same asset class
    yfinance already covers, demonstrating multi-vendor pluggability. Uses the
    market_chart/range endpoint (a price series, not true intrabar OHLC) and
    resamples to daily open/high/low/close/volume; treat as a cross-check source
    the same way Stooq is for equities, not a silent substitute for yfinance."""

    name = "coingecko"

    def fetch(self, symbols: Sequence[str], start: date, end: date, interval: str = "1d") -> pd.DataFrame:
        frames = [self._fetch_one(symbol, start, end) for symbol in symbols]
        combined = pd.concat(frames, ignore_index=True)
        return normalize_ohlcv(combined, self.name)

    def _fetch_one(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        coin_id = _to_coingecko_id(symbol)
        from_ts = int(pd.Timestamp(start).timestamp())
        to_ts = int(pd.Timestamp(end).timestamp()) + 86_400  # inclusive of the end day

        try:
            response = requests.get(
                f"{BASE_URL}/coins/{coin_id}/market_chart/range",
                params={"vs_currency": "usd", "from": from_ts, "to": to_ts},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise DataSourceError(f"coingecko fetch failed for {symbol}: {exc}") from exc

        prices = payload.get("prices", [])
        if not prices:
            raise DataSourceError(f"coingecko returned no data for {symbol} [{start}..{end}]")
        volumes = payload.get("total_volumes", [])

        price_df = pd.DataFrame(prices, columns=["ts", "price"])
        price_df["date"] = pd.to_datetime(price_df["ts"], unit="ms").dt.normalize()
        daily = price_df.groupby("date")["price"].agg(["first", "max", "min", "last"])
        daily.columns = ["open", "high", "low", "close"]

        if volumes:
            vol_df = pd.DataFrame(volumes, columns=["ts", "volume"])
            vol_df["date"] = pd.to_datetime(vol_df["ts"], unit="ms").dt.normalize()
            daily["volume"] = vol_df.groupby("date")["volume"].last()
        else:
            daily["volume"] = 0.0

        out = daily.reset_index()
        out["symbol"] = symbol
        out["adj_close"] = out["close"]
        return out
