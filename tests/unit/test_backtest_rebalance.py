from __future__ import annotations

import numpy as np
import pandas as pd

from quant_research.backtest.rebalance import apply_rebalance_schedule


def test_daily_is_a_noop() -> None:
    dates = pd.bdate_range("2020-01-01", periods=10)
    weights = pd.DataFrame({"AAA": np.linspace(0, 1, 10)}, index=dates)
    result = apply_rebalance_schedule(weights, "daily")
    pd.testing.assert_frame_equal(result, weights)


def test_weekly_holds_weight_constant_within_week() -> None:
    dates = pd.bdate_range("2020-01-06", periods=10)  # Mon 2020-01-06 .. Fri 2020-01-17
    # a different weight every day -- weekly rebalance should collapse each week to one value
    weights = pd.DataFrame({"AAA": np.arange(10, dtype=float)}, index=dates)

    result = apply_rebalance_schedule(weights, "weekly")

    week1 = result.loc["2020-01-06":"2020-01-10", "AAA"]
    week2 = result.loc["2020-01-13":"2020-01-17", "AAA"]
    assert week1.nunique() == 1
    assert week2.nunique() == 1
    assert week1.iloc[0] == weights["AAA"].iloc[0]  # Monday's signal carried through the week
    assert week2.iloc[0] == weights["AAA"].iloc[5]  # next Monday's signal starts the new week


def test_monthly_holds_weight_constant_within_month() -> None:
    dates = pd.bdate_range("2020-01-01", "2020-03-31")
    weights = pd.DataFrame({"AAA": np.linspace(0, 1, len(dates))}, index=dates)

    result = apply_rebalance_schedule(weights, "monthly")

    for month in ["2020-01", "2020-02", "2020-03"]:
        assert result.loc[month, "AAA"].nunique() == 1


def test_reduces_turnover_versus_daily_rebalance() -> None:
    dates = pd.bdate_range("2020-01-01", periods=60)
    rng = np.random.default_rng(9)
    noisy_weights = pd.DataFrame({"AAA": rng.uniform(-1, 1, 60)}, index=dates)

    daily_turnover = noisy_weights.diff().abs().sum().sum()
    monthly = apply_rebalance_schedule(noisy_weights, "monthly")
    monthly_turnover = monthly.diff().abs().sum().sum()

    assert monthly_turnover < daily_turnover


def test_empty_weights_returns_empty() -> None:
    weights = pd.DataFrame(columns=["AAA"])
    result = apply_rebalance_schedule(weights, "weekly")
    assert result.empty
