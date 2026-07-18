from __future__ import annotations

import numpy as np
import pandas as pd

from quant_research.core.registries import STRATEGY_REGISTRY
from quant_research.strategy.base import Strategy


@STRATEGY_REGISTRY.register("top_bottom_decile_ew")
class TopBottomDecileEqualWeight(Strategy):
    """Simpler alternative to rank-weighted: equal-weight long the top decile
    (default `n_quantiles=10`), equal-weight short the bottom decile, gross
    exposure = 1.0 (0.5 long + 0.5 short)."""

    name = "top_bottom_decile_ew"

    def generate_weights(self, signal_df: pd.DataFrame, prices: pd.DataFrame | None = None) -> pd.DataFrame:
        n_quantiles = int(self.params.get("n_quantiles", 10))
        cutoff = 1.0 / n_quantiles

        ranks = signal_df.rank(axis=1, pct=True, na_option="keep")
        top_mask = ranks >= (1 - cutoff)
        bottom_mask = ranks <= cutoff

        top_count = top_mask.sum(axis=1).replace(0, np.nan)
        bottom_count = bottom_mask.sum(axis=1).replace(0, np.nan)

        long_weights = top_mask.div(top_count, axis=0).fillna(0.0) * 0.5
        short_weights = bottom_mask.div(bottom_count, axis=0).fillna(0.0) * -0.5

        return long_weights + short_weights
