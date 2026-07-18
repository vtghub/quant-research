from __future__ import annotations

import pandas as pd

from quant_research.core.registries import SIGNAL_REGISTRY
from quant_research.signals.base import Signal


@SIGNAL_REGISTRY.register("rsi")
class RSISignal(Signal):
    """Wilder's RSI (0-100) via an EWM average of gains/losses."""

    name = "rsi"

    def compute(self, prices: pd.DataFrame, inputs: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
        window = int(self.params.get("window", 14))
        delta = prices.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
        avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
