from __future__ import annotations

import numpy as np
import pandas as pd

from quant_research.signals.library.mean_reversion import MeanReversionZScoreSignal


def test_unusually_negative_return_gives_positive_score() -> None:
    dates = pd.bdate_range("2020-01-01", periods=30)
    rng = np.random.default_rng(4)
    small_moves = rng.normal(0, 0.001, 29)
    prices_vals = [100.0]
    for m in small_moves[:-1]:
        prices_vals.append(prices_vals[-1] * (1 + m))
    prices_vals.append(prices_vals[-1] * 0.90)  # sharp drop on the last day
    prices = pd.DataFrame({"AAA": prices_vals}, index=dates)

    signal = MeanReversionZScoreSignal(window=20)
    result = signal.compute(prices)
    assert result["AAA"].iloc[-1] > 0  # sharp drop -> expect reversion up -> positive score


def test_unusually_positive_return_gives_negative_score() -> None:
    dates = pd.bdate_range("2020-01-01", periods=30)
    rng = np.random.default_rng(5)
    small_moves = rng.normal(0, 0.001, 29)
    prices_vals = [100.0]
    for m in small_moves[:-1]:
        prices_vals.append(prices_vals[-1] * (1 + m))
    prices_vals.append(prices_vals[-1] * 1.10)  # sharp spike on the last day
    prices = pd.DataFrame({"AAA": prices_vals}, index=dates)

    signal = MeanReversionZScoreSignal(window=20)
    result = signal.compute(prices)
    assert result["AAA"].iloc[-1] < 0
