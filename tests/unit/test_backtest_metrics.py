from __future__ import annotations

import numpy as np
import pandas as pd

from quant_research.backtest.metrics import (
    annualized_vol,
    cagr,
    calmar_ratio,
    compute_metrics,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
)


def test_max_drawdown_on_known_path() -> None:
    equity = pd.Series([100.0, 120.0, 90.0, 95.0, 130.0])
    # peak 120 -> trough 90 => -25%
    assert np.isclose(max_drawdown(equity), -0.25)


def test_max_drawdown_monotonic_up_is_zero() -> None:
    equity = pd.Series([100.0, 101.0, 102.0, 110.0])
    assert max_drawdown(equity) == 0.0


def test_cagr_doubling_in_one_year() -> None:
    equity = pd.Series([100.0] + [100.0] * 251 + [200.0])  # 253 points ~ 1yr of trading days
    result = cagr(equity, periods_per_year=252)
    assert result > 0.9  # should be close to 100% annual growth


def test_zero_vol_series_has_zero_sharpe_and_vol() -> None:
    flat = pd.Series([0.0] * 100)
    assert sharpe_ratio(flat) == 0.0
    assert annualized_vol(flat) == 0.0
    assert sortino_ratio(flat) == 0.0


def test_sharpe_positive_for_consistently_positive_returns() -> None:
    rng = np.random.default_rng(1)
    returns = pd.Series(rng.normal(0.001, 0.005, 500))
    assert sharpe_ratio(returns) > 0


def test_calmar_zero_when_no_drawdown() -> None:
    equity = pd.Series([100.0, 101.0, 102.0])
    assert calmar_ratio(equity) == 0.0


def test_compute_metrics_returns_all_keys() -> None:
    rng = np.random.default_rng(2)
    returns = pd.Series(rng.normal(0.0003, 0.01, 300))
    equity = 1_000_000 * (1 + returns).cumprod()
    metrics = compute_metrics(returns, equity)
    for key in ("cagr", "annualized_vol", "sharpe", "sortino", "max_drawdown", "calmar", "total_return"):
        assert key in metrics
        assert np.isfinite(metrics[key])
