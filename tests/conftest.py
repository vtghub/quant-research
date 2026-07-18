from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # never open a display / write a real window in tests

import numpy as np
import pandas as pd
import pytest


SYMBOLS = ["AAA", "BBB", "CCC", "DDD", "EEE"]


@pytest.fixture
def synthetic_prices() -> pd.DataFrame:
    """Deterministic GBM-like wide price panel: date-indexed, columns=symbols."""
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2020-01-01", periods=500)
    n, k = len(dates), len(SYMBOLS)
    drift = rng.uniform(-0.0002, 0.0004, size=k)
    vol = rng.uniform(0.01, 0.02, size=k)
    shocks = rng.normal(0.0, 1.0, size=(n, k)) * vol + drift
    log_prices = np.cumsum(shocks, axis=0)
    prices = 100.0 * np.exp(log_prices)
    return pd.DataFrame(prices, index=dates, columns=SYMBOLS)


@pytest.fixture
def synthetic_long_ohlcv(synthetic_prices: pd.DataFrame) -> pd.DataFrame:
    """The same panel reshaped into the long OHLCV schema data sources return."""
    frames = []
    for symbol in synthetic_prices.columns:
        close = synthetic_prices[symbol]
        frames.append(
            pd.DataFrame(
                {
                    "date": close.index,
                    "symbol": symbol,
                    "open": close.values,
                    "high": close.values * 1.001,
                    "low": close.values * 0.999,
                    "close": close.values,
                    "adj_close": close.values,
                    "volume": 1_000_000,
                    "source": "fake",
                }
            )
        )
    return pd.concat(frames, ignore_index=True).sort_values(["symbol", "date"]).reset_index(drop=True)


class FakeDataSource:
    """OHLCVDataSource-shaped test double backed by an in-memory long frame -- no network."""

    name = "fake"

    def __init__(self, long_df: pd.DataFrame) -> None:
        self._long_df = long_df

    def fetch(self, symbols, start, end, interval="1d") -> pd.DataFrame:
        start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
        mask = (
            self._long_df["symbol"].isin(symbols)
            & (self._long_df["date"] >= start_ts)
            & (self._long_df["date"] <= end_ts)
        )
        sliced = self._long_df.loc[mask].copy()
        sliced["source"] = self.name
        return sliced.sort_values(["symbol", "date"]).reset_index(drop=True)


@pytest.fixture
def fake_data_source(synthetic_long_ohlcv: pd.DataFrame) -> FakeDataSource:
    return FakeDataSource(synthetic_long_ohlcv)
