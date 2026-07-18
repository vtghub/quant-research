from __future__ import annotations

from typing import Sequence

import pandas as pd


def forward_returns(prices: pd.DataFrame, horizons: Sequence[int]) -> dict[int, pd.DataFrame]:
    """out[h].loc[t] = price_{t+h} / price_t - 1 -- the return over the h days
    following t, for a signal computed using only information through t. This is
    the same t -> t+1 no-lookahead convention BacktestEngine enforces via its
    weights.shift(1) (a weight decided at t-1 earns exactly price_t/price_{t-1}-1,
    i.e. BacktestEngine's realized daily_returns.loc[t] == forward_returns(...)[1].loc[t-1]),
    encoded independently here since IC screening never runs through the backtest
    engine -- see the cross-check test in tests/unit/test_lookahead_convention.py."""
    return {h: prices.shift(-h) / prices - 1.0 for h in horizons}
