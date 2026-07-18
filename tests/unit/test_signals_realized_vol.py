from __future__ import annotations

import numpy as np
import pandas as pd

from quant_research.signals.library.realized_vol import RealizedVolatilitySignal


def test_higher_variance_series_has_higher_realized_vol() -> None:
    dates = pd.bdate_range("2020-01-01", periods=100)
    rng = np.random.default_rng(6)
    calm_returns = rng.normal(0, 0.001, 100)
    volatile_returns = rng.normal(0, 0.05, 100)
    calm_prices = 100 * (1 + pd.Series(calm_returns)).cumprod()
    volatile_prices = 100 * (1 + pd.Series(volatile_returns)).cumprod()
    prices = pd.DataFrame({"CALM": calm_prices.values, "VOL": volatile_prices.values}, index=dates)

    signal = RealizedVolatilitySignal(window=20)
    result = signal.compute(prices)

    assert result["VOL"].iloc[-1] > result["CALM"].iloc[-1]


def test_zero_variance_gives_zero_vol() -> None:
    dates = pd.bdate_range("2020-01-01", periods=30)
    prices = pd.DataFrame({"AAA": [100.0] * 30}, index=dates)
    signal = RealizedVolatilitySignal(window=20)
    result = signal.compute(prices)
    assert np.isclose(result["AAA"].iloc[-1], 0.0)


def test_annualization_scales_result() -> None:
    dates = pd.bdate_range("2020-01-01", periods=60)
    rng = np.random.default_rng(7)
    prices = pd.DataFrame({"AAA": 100 * (1 + pd.Series(rng.normal(0, 0.01, 60))).cumprod().values}, index=dates)
    low = RealizedVolatilitySignal(window=20, annualization=1).compute(prices)
    high = RealizedVolatilitySignal(window=20, annualization=252).compute(prices)
    ratio = (high["AAA"] / low["AAA"]).dropna()
    assert np.allclose(ratio, np.sqrt(252), atol=1e-6)
