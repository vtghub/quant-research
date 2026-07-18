from __future__ import annotations

import pandas as pd

from quant_research.core.registries import SIGNAL_REGISTRY
from quant_research.signals.base import Signal


@SIGNAL_REGISTRY.register("momentum")
class MomentumSignal(Signal):
    """Classic 12-1 style momentum: return over `lookback` days, skipping the most
    recent `skip_recent` days to avoid the short-term reversal effect."""

    name = "momentum"

    def compute(self, prices: pd.DataFrame, inputs: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
        lookback = int(self.params.get("lookback", 126))
        skip_recent = int(self.params.get("skip_recent", 21))
        recent = prices.shift(skip_recent)
        past = prices.shift(skip_recent + lookback)
        return recent / past - 1.0
