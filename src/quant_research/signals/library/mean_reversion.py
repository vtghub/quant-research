from __future__ import annotations

import pandas as pd

from quant_research.core.registries import SIGNAL_REGISTRY
from quant_research.signals.base import Signal


@SIGNAL_REGISTRY.register("zscore_meanrev")
class MeanReversionZScoreSignal(Signal):
    """Rolling z-score of *returns* (not price level), sign-flipped so a positive
    score means the recent return was unusually low -- i.e. "expect reversion up"."""

    name = "zscore_meanrev"

    def compute(self, prices: pd.DataFrame, inputs: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
        window = int(self.params.get("window", 20))
        returns = prices.pct_change()
        rolling_mean = returns.rolling(window).mean()
        rolling_std = returns.rolling(window).std(ddof=0)
        z = (returns - rolling_mean) / rolling_std
        return -z
