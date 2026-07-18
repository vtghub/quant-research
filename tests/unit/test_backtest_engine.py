from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant_research.backtest.costs import BpsCostModel, CostModel
from quant_research.backtest.engine import BacktestEngine


class ZeroCostModel(CostModel):
    def cost(self, weight_diff, prices=None):
        return pd.Series(0.0, index=weight_diff.index)


@pytest.fixture
def deterministic_setup():
    dates = pd.bdate_range("2021-01-04", periods=3)  # Mon, Tue, Wed
    prices = pd.DataFrame({"A": [100.0, 110.0, 121.0], "B": [100.0, 100.0, 100.0]}, index=dates)
    weights = pd.DataFrame({"A": [1.0, 1.0, 1.0], "B": [0.0, 0.0, 0.0]}, index=dates)
    return prices, weights


def test_zero_day_zero_weight_means_zero_first_day_pnl(deterministic_setup) -> None:
    prices, weights = deterministic_setup
    engine = BacktestEngine(ZeroCostModel(), initial_capital=1_000_000.0)
    result = engine.run(weights, prices)

    assert np.isclose(result.daily_returns.iloc[0], 0.0)
    assert np.isclose(result.equity_curve.iloc[0], 1_000_000.0)


def test_lookahead_shift_hand_computed_pnl(deterministic_setup) -> None:
    """A weight decided on day t must only earn the return realized from t->t+1,
    never the same-day return -- this is the core no-lookahead guarantee."""
    prices, weights = deterministic_setup
    engine = BacktestEngine(ZeroCostModel(), initial_capital=1_000_000.0)
    result = engine.run(weights, prices)

    # day1: A return is 110/100-1=0.10, realized weight on day1 is day0's weight (A=1.0)
    assert np.isclose(result.daily_returns.iloc[1], 0.10)
    # day2: A return is 121/110-1=0.10, realized weight is day1's weight (A=1.0)
    assert np.isclose(result.daily_returns.iloc[2], 0.10)

    expected_equity = 1_000_000.0 * np.array([1.0, 1.10, 1.10 * 1.10])
    assert np.allclose(result.equity_curve.values, expected_equity)


def test_turnover_and_cost_model_applied(deterministic_setup) -> None:
    prices, weights = deterministic_setup
    engine = BacktestEngine(BpsCostModel(bps_per_trade=100.0), initial_capital=1_000_000.0)  # 100bps = 1%
    result = engine.run(weights, prices)

    # turnover: day0 realized weight already 0 -> 0 diff; day1 realized weight jumps
    # from 0 to [1,0] -> turnover 1.0; day2 weight unchanged -> turnover 0.
    assert np.isclose(result.turnover.iloc[0], 0.0)
    assert np.isclose(result.turnover.iloc[1], 1.0)
    assert np.isclose(result.turnover.iloc[2], 0.0)

    assert np.isclose(result.trade_cost.iloc[1], 0.01)
    # day1 net pnl = gross 0.10 - cost 0.01
    assert np.isclose(result.daily_returns.iloc[1], 0.09)


def test_result_contains_computed_metrics(deterministic_setup) -> None:
    prices, weights = deterministic_setup
    engine = BacktestEngine(ZeroCostModel())
    result = engine.run(weights, prices)
    assert "sharpe" in result.metrics
    assert "max_drawdown" in result.metrics
    assert np.isfinite(result.metrics["sharpe"])


def test_flat_weights_never_traded_zero_turnover() -> None:
    dates = pd.bdate_range("2021-01-04", periods=4)
    prices = pd.DataFrame({"A": [100.0, 101.0, 99.0, 102.0]}, index=dates)
    weights = pd.DataFrame({"A": [0.0, 0.0, 0.0, 0.0]}, index=dates)
    engine = BacktestEngine(BpsCostModel(bps_per_trade=10.0))
    result = engine.run(weights, prices)
    assert np.allclose(result.turnover.values, 0.0)
    assert np.allclose(result.trade_cost.values, 0.0)
    assert np.allclose(result.equity_curve.values, 1_000_000.0)
