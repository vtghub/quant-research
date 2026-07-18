from __future__ import annotations

import numpy as np
import pandas as pd

from quant_research.core.registries import SIGNAL_REGISTRY
from quant_research.signals.base import Signal


@SIGNAL_REGISTRY.register("breakout")
class BreakoutSignal(Signal):
    """Donchian-channel breakout: position of price relative to the prior
    `window`-day high/low channel (excluding today, so a genuine breakout can
    score outside [-1, 1] -- e.g. +1.3 means price is 30% of the channel's
    width above the prior high)."""

    name = "breakout"

    def compute(self, prices: pd.DataFrame, inputs: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
        window = int(self.params.get("window", 20))
        prior = prices.shift(1)
        prior_high = prior.rolling(window).max()
        prior_low = prior.rolling(window).min()
        channel_range = (prior_high - prior_low).replace(0.0, np.nan)
        return 2.0 * (prices - prior_low) / channel_range - 1.0
