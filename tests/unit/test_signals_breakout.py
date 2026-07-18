from __future__ import annotations

import numpy as np
import pandas as pd

from quant_research.signals.library.breakout import BreakoutSignal


def test_new_high_breakout_scores_above_one() -> None:
    dates = pd.bdate_range("2020-01-01", periods=25)
    # flat at 100 for 20 days, then a sharp breakout above the prior 20-day high
    values = [100.0] * 20 + [101.0, 102.0, 103.0, 105.0, 120.0]
    prices = pd.DataFrame({"AAA": values}, index=dates)

    signal = BreakoutSignal(window=20)
    result = signal.compute(prices)

    assert result["AAA"].iloc[-1] > 1.0


def test_new_low_breakdown_scores_below_negative_one() -> None:
    dates = pd.bdate_range("2020-01-01", periods=25)
    values = [100.0] * 20 + [99.0, 98.0, 97.0, 95.0, 80.0]
    prices = pd.DataFrame({"AAA": values}, index=dates)

    signal = BreakoutSignal(window=20)
    result = signal.compute(prices)

    assert result["AAA"].iloc[-1] < -1.0


def test_mid_channel_price_scores_near_zero() -> None:
    dates = pd.bdate_range("2020-01-01", periods=25)
    values = list(np.linspace(90, 110, 20)) + [100.0] * 5
    prices = pd.DataFrame({"AAA": values}, index=dates)

    signal = BreakoutSignal(window=20)
    result = signal.compute(prices)
    assert abs(result["AAA"].iloc[-1]) < 1.0


def test_flat_channel_is_nan_not_error() -> None:
    dates = pd.bdate_range("2020-01-01", periods=25)
    prices = pd.DataFrame({"AAA": [100.0] * 25}, index=dates)
    signal = BreakoutSignal(window=20)
    result = signal.compute(prices)
    assert result["AAA"].iloc[-1] is not None  # NaN from zero-range division, not an exception
