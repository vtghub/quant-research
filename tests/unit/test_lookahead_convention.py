from __future__ import annotations

import numpy as np
import pandas as pd

from quant_research.backtest.costs import CostModel
from quant_research.backtest.engine import BacktestEngine
from quant_research.research.forward_returns import forward_returns


class ZeroCostModel(CostModel):
    def cost(self, weight_diff, prices=None):
        return pd.Series(0.0, index=weight_diff.index)


def test_backtest_realized_return_matches_forward_returns_one_day_offset() -> None:
    """The two independent t -> t+1 implementations (BacktestEngine's weight
    shift, and research/forward_returns) must never drift apart: a weight
    decided at date t-1 realizes exactly forward_returns(...)[1].loc[t-1] at
    date t inside the backtest."""
    dates = pd.bdate_range("2021-01-04", periods=10)
    rng = np.random.default_rng(42)
    prices = pd.DataFrame(
        {"AAA": 100.0 * (1 + rng.normal(0.0005, 0.01, 10)).cumprod()}, index=dates
    )
    weights = pd.DataFrame({"AAA": 1.0}, index=dates)  # always fully long

    engine = BacktestEngine(ZeroCostModel(), initial_capital=1.0)
    bt_result = engine.run(weights, prices)

    fwd = forward_returns(prices, horizons=[1])
    expected = fwd[1]["AAA"].shift(1)  # forward_returns computed at t-1, realized at t

    aligned_actual, aligned_expected = bt_result.daily_returns.iloc[1:-1].align(expected.iloc[1:-1])
    assert np.allclose(aligned_actual.values, aligned_expected.values, equal_nan=False)


def test_multi_symbol_backtest_matches_forward_returns_per_symbol() -> None:
    dates = pd.bdate_range("2021-01-04", periods=15)
    rng = np.random.default_rng(7)
    prices = pd.DataFrame(
        {
            "AAA": 100.0 * (1 + rng.normal(0.0, 0.01, 15)).cumprod(),
            "BBB": 50.0 * (1 + rng.normal(0.0, 0.02, 15)).cumprod(),
        },
        index=dates,
    )
    # single-symbol weight at a time, isolating each symbol's contribution
    for symbol in prices.columns:
        weights = pd.DataFrame(0.0, index=dates, columns=prices.columns)
        weights[symbol] = 1.0

        engine = BacktestEngine(ZeroCostModel(), initial_capital=1.0)
        bt_result = engine.run(weights, prices)

        fwd = forward_returns(prices, horizons=[1])
        expected = fwd[1][symbol].shift(1)

        aligned_actual, aligned_expected = bt_result.daily_returns.iloc[1:-1].align(expected.iloc[1:-1])
        assert np.allclose(aligned_actual.values, aligned_expected.values, equal_nan=False)
