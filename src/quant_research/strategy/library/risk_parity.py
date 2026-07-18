from __future__ import annotations

import numpy as np
import pandas as pd

from quant_research.core.exceptions import ConfigError
from quant_research.core.registries import STRATEGY_REGISTRY
from quant_research.strategy.base import Strategy


@STRATEGY_REGISTRY.register("risk_parity")
class RiskParityStrategy(Strategy):
    """Inverse-volatility weighted, long-only: by default restricts to symbols
    with a positive signal that day (params.require_positive_signal=True), then
    weights the eligible symbols inversely proportional to trailing realized
    volatility (params.vol_lookback, default 20 trading days), normalized so
    gross exposure = 1.0 each day. Set require_positive_signal=False for pure
    signal-agnostic risk parity across the whole universe."""

    name = "risk_parity"

    def generate_weights(self, signal_df: pd.DataFrame, prices: pd.DataFrame | None = None) -> pd.DataFrame:
        if prices is None:
            raise ConfigError("risk_parity strategy requires prices to compute trailing volatility")

        vol_lookback = int(self.params.get("vol_lookback", 20))
        require_positive_signal = bool(self.params.get("require_positive_signal", True))

        trailing_vol = prices.pct_change().rolling(vol_lookback).std(ddof=0)
        inv_vol = (1.0 / trailing_vol.replace(0.0, np.nan)).reindex(columns=signal_df.columns)

        if require_positive_signal:
            eligible = signal_df > 0
            inv_vol = inv_vol.where(eligible, 0.0)

        gross = inv_vol.abs().sum(axis=1).replace(0.0, np.nan)
        return inv_vol.div(gross, axis=0).fillna(0.0)
