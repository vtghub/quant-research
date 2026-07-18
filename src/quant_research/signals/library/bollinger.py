from __future__ import annotations

import pandas as pd

from quant_research.core.registries import SIGNAL_REGISTRY
from quant_research.signals.base import Signal


@SIGNAL_REGISTRY.register("bollinger_z")
class BollingerZSignal(Signal):
    """Rolling z-score of price level against its own rolling mean/std, scaled by
    `num_std` so a score of +-1.0 corresponds to touching the Bollinger band."""

    name = "bollinger_z"

    def compute(self, prices: pd.DataFrame, inputs: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
        window = int(self.params.get("window", 20))
        num_std = float(self.params.get("num_std", 2.0))

        rolling_mean = prices.rolling(window).mean()
        rolling_std = prices.rolling(window).std(ddof=0)
        z = (prices - rolling_mean) / rolling_std
        return z / num_std
