from __future__ import annotations

import numpy as np
import pandas as pd

from quant_research.core.registries import SIGNAL_REGISTRY
from quant_research.signals.base import Signal


@SIGNAL_REGISTRY.register("realized_vol")
class RealizedVolatilitySignal(Signal):
    """Annualized rolling realized volatility of returns. Usable directly as a
    risk-sizing input (see strategy/vol_target.py), or as a "low-vol anomaly"
    alpha signal when combined with a negative weight in a composite (lower
    realized vol has historically earned better risk-adjusted returns)."""

    name = "realized_vol"

    def compute(self, prices: pd.DataFrame, inputs: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
        window = int(self.params.get("window", 20))
        annualization = float(self.params.get("annualization", 252))
        returns = prices.pct_change()
        return returns.rolling(window).std(ddof=0) * np.sqrt(annualization)
