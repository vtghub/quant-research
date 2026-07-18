from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from quant_research.backtest.costs import CostModel
from quant_research.backtest.metrics import compute_metrics


@dataclass
class BacktestResult:
    equity_curve: pd.Series
    daily_returns: pd.Series
    weights: pd.DataFrame
    turnover: pd.Series
    trade_cost: pd.Series
    metrics: dict[str, float]


class BacktestEngine:
    """Vectorized pandas backtest. This class is the SOLE place in the codebase
    that shifts weights by one day before applying them to returns -- Strategy
    implementations must decide weights using only same-day-or-earlier information
    and must NOT pre-shift; research/forward_returns.py encodes the same t -> t+1
    convention independently for IC analysis (see tests/unit/test_lookahead_convention.py
    which cross-checks the two never drift apart)."""

    def __init__(self, cost_model: CostModel, initial_capital: float = 1_000_000.0) -> None:
        self.cost_model = cost_model
        self.initial_capital = initial_capital

    def run(self, weights: pd.DataFrame, prices: pd.DataFrame) -> BacktestResult:
        daily_returns_raw = prices.pct_change()

        # The one and only lookahead-protection shift: a weight decided using
        # information through date t is not earned until the return realized
        # from t to t+1.
        realized_weights = weights.shift(1).reindex(daily_returns_raw.index).fillna(0.0)

        gross_pnl = (realized_weights * daily_returns_raw).sum(axis=1)

        weight_diff = realized_weights.diff()
        weight_diff.iloc[0] = realized_weights.iloc[0]

        trade_cost = self.cost_model.cost(weight_diff, prices)
        net_pnl = gross_pnl - trade_cost

        equity_curve = self.initial_capital * (1.0 + net_pnl).cumprod()
        turnover = weight_diff.abs().sum(axis=1)

        return BacktestResult(
            equity_curve=equity_curve,
            daily_returns=net_pnl,
            weights=realized_weights,
            turnover=turnover,
            trade_cost=trade_cost,
            metrics=compute_metrics(net_pnl, equity_curve),
        )
