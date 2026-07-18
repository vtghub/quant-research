from __future__ import annotations

import numpy as np
import pandas as pd

from quant_research.signals.library.macd import MACDSignal


def test_macd_positive_for_accelerating_uptrend() -> None:
    dates = pd.bdate_range("2020-01-01", periods=100)
    # exponential growth -> fast EMA pulls ahead of slow EMA -> positive histogram late
    prices = pd.DataFrame({"AAA": 100.0 * (1.01 ** np.arange(100))}, index=dates)
    signal = MACDSignal(fast=12, slow=26, signal=9)
    result = signal.compute(prices)
    assert (result["AAA"].iloc[-10:] > 0).all()


def test_macd_zero_for_flat_price() -> None:
    dates = pd.bdate_range("2020-01-01", periods=60)
    prices = pd.DataFrame({"AAA": [100.0] * 60}, index=dates)
    signal = MACDSignal()
    result = signal.compute(prices)
    assert np.allclose(result["AAA"].iloc[30:], 0.0, atol=1e-9)


def test_macd_output_same_shape_as_prices() -> None:
    dates = pd.bdate_range("2020-01-01", periods=40)
    prices = pd.DataFrame({"AAA": np.linspace(100, 110, 40), "BBB": np.linspace(50, 45, 40)}, index=dates)
    signal = MACDSignal()
    result = signal.compute(prices)
    assert result.shape == prices.shape
