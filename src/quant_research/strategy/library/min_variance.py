from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from quant_research.core.exceptions import ConfigError
from quant_research.core.registries import STRATEGY_REGISTRY
from quant_research.strategy.base import Strategy


def _solve_min_variance(cov: np.ndarray) -> np.ndarray | None:
    """Long-only min-variance weights via scipy SLSQP: minimize w'Sw subject to
    sum(w)=1, w>=0. Returns None if the optimizer doesn't converge (e.g. a
    near-singular covariance matrix), so the caller can fall back to equal
    weight rather than propagate a bad solution."""
    n = cov.shape[0]
    x0 = np.full(n, 1.0 / n)
    bounds = [(0.0, 1.0)] * n
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

    result = minimize(lambda w: w @ cov @ w, x0, method="SLSQP", bounds=bounds, constraints=constraints)
    return result.x if result.success else None


@STRATEGY_REGISTRY.register("min_variance")
class MinVarianceStrategy(Strategy):
    """Long-only minimum-variance portfolio: on each date, solves
    min w'Sw s.t. sum(w)=1, w>=0 (scipy SLSQP) where S is the trailing sample
    covariance matrix of returns over params.lookback (default 60 trading
    days, using only the window strictly before that date -- no lookahead).
    By default restricts to symbols with a positive signal that day
    (params.require_positive_signal=True, matching risk_parity's convention).
    Falls back to equal weight among eligible symbols if optimization doesn't
    converge. O(n_dates) with one optimization per date -- fine for research-
    scale universes/date-ranges, not intended for very large or high-frequency
    backtests."""

    name = "min_variance"

    def generate_weights(self, signal_df: pd.DataFrame, prices: pd.DataFrame | None = None) -> pd.DataFrame:
        if prices is None:
            raise ConfigError("min_variance strategy requires prices to compute a covariance matrix")

        lookback = int(self.params.get("lookback", 60))
        require_positive_signal = bool(self.params.get("require_positive_signal", True))
        returns = prices.pct_change()

        weights = pd.DataFrame(0.0, index=signal_df.index, columns=signal_df.columns)

        for i, date_idx in enumerate(prices.index):
            if i < lookback or date_idx not in signal_df.index:
                continue

            if require_positive_signal:
                eligible_mask = signal_df.loc[date_idx] > 0
            else:
                eligible_mask = pd.Series(True, index=signal_df.columns)

            window_returns = returns.iloc[i - lookback : i]
            symbols = [
                s
                for s in signal_df.columns
                if bool(eligible_mask.get(s, False)) and s in window_returns.columns and window_returns[s].notna().all()
            ]
            if len(symbols) < 2:
                continue

            cov = window_returns[symbols].cov().values
            w = _solve_min_variance(cov)
            if w is None:
                w = np.full(len(symbols), 1.0 / len(symbols))
            weights.loc[date_idx, symbols] = w

        return weights
