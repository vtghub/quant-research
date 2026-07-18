from __future__ import annotations

import numpy as np
import pandas as pd

from quant_research.core.exceptions import ConfigError
from quant_research.core.registries import STRATEGY_REGISTRY
from quant_research.strategy.base import Strategy


def apply_vol_target(
    weights: pd.DataFrame,
    prices: pd.DataFrame,
    target_annual_vol: float,
    lookback: int = 20,
    max_leverage: float = 3.0,
) -> pd.DataFrame:
    """Rescale a weight matrix day by day so trailing realized portfolio vol
    matches `target_annual_vol`, clipped to `max_leverage`. Uses the same
    weights.shift(1) convention as BacktestEngine to estimate trailing portfolio
    returns (an approximation for sizing purposes -- the backtest itself still
    owns the authoritative lookahead-protection shift)."""
    returns = prices.pct_change()
    realized_weights = weights.shift(1).reindex(returns.index).fillna(0.0)
    portfolio_returns = (realized_weights * returns).sum(axis=1)
    trailing_vol = portfolio_returns.rolling(lookback).std(ddof=0) * np.sqrt(252)

    scale = target_annual_vol / trailing_vol
    scale = scale.replace([np.inf, -np.inf], max_leverage).clip(upper=max_leverage).fillna(0.0)
    return weights.mul(scale, axis=0)


@STRATEGY_REGISTRY.register("vol_targeted")
class VolTargetedStrategy(Strategy):
    """Wraps an inner strategy (pulled from STRATEGY_REGISTRY by name) and
    rescales its output to a target annualized volatility -- a concrete example
    of strategies composing other registry entries rather than only signals."""

    name = "vol_targeted"

    def generate_weights(self, signal_df: pd.DataFrame, prices: pd.DataFrame | None = None) -> pd.DataFrame:
        if prices is None:
            raise ConfigError("vol_targeted strategy requires prices to estimate trailing portfolio vol")

        inner_name = self.params.get("inner_strategy")
        if not inner_name:
            raise ConfigError("vol_targeted strategy requires params.inner_strategy")
        inner_params = self.params.get("inner_params", {})
        inner = STRATEGY_REGISTRY.create(inner_name, **inner_params)
        base_weights = inner.generate_weights(signal_df, prices)

        target_annual_vol = float(self.params.get("target_annual_vol", 0.10))
        lookback = int(self.params.get("lookback", 20))
        max_leverage = float(self.params.get("max_leverage", 3.0))
        return apply_vol_target(base_weights, prices, target_annual_vol, lookback, max_leverage)
