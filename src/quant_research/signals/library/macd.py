from __future__ import annotations

import pandas as pd

from quant_research.core.registries import SIGNAL_REGISTRY
from quant_research.signals.base import Signal


@SIGNAL_REGISTRY.register("macd")
class MACDSignal(Signal):
    """MACD histogram: (EMA_fast - EMA_slow) minus its own EMA(signal) smoothing."""

    name = "macd"

    def compute(self, prices: pd.DataFrame, inputs: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
        fast = int(self.params.get("fast", 12))
        slow = int(self.params.get("slow", 26))
        signal_window = int(self.params.get("signal", 9))

        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal_window, adjust=False).mean()
        return macd_line - signal_line
