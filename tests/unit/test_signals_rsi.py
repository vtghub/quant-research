from __future__ import annotations

import numpy as np
import pandas as pd

from quant_research.signals.library.rsi import RSISignal


def test_rsi_approaches_100_for_monotonic_uptrend() -> None:
    dates = pd.bdate_range("2020-01-01", periods=60)
    prices = pd.DataFrame({"AAA": np.linspace(100, 200, 60)}, index=dates)
    signal = RSISignal(window=14)
    result = signal.compute(prices)
    assert result["AAA"].iloc[-1] > 95


def test_rsi_approaches_0_for_monotonic_downtrend() -> None:
    dates = pd.bdate_range("2020-01-01", periods=60)
    prices = pd.DataFrame({"AAA": np.linspace(200, 100, 60)}, index=dates)
    signal = RSISignal(window=14)
    result = signal.compute(prices)
    assert result["AAA"].iloc[-1] < 5


def test_rsi_flat_price_is_undefined_not_error() -> None:
    dates = pd.bdate_range("2020-01-01", periods=30)
    prices = pd.DataFrame({"AAA": [100.0] * 30}, index=dates)
    signal = RSISignal(window=14)
    result = signal.compute(prices)
    # no gains or losses -> 0/0 -> NaN, must not raise
    assert result["AAA"].iloc[-1] is not None
