from __future__ import annotations

import pandas as pd

from quant_research.core.registries import STRATEGY_REGISTRY
from quant_research.strategy.base import Strategy


@STRATEGY_REGISTRY.register("rank_weighted_long_short")
class RankWeightedLongShort(Strategy):
    """Cross-sectional rank-weighted long/short: percentile-ranks the signal each
    day, longs the top `top_frac`, shorts the bottom `bottom_frac`, weights within
    each side proportional to (rank - 0.5), and normalizes so gross exposure = 1.0
    (0.5 long + 0.5 short) -- dollar-neutral by construction."""

    name = "rank_weighted_long_short"

    def generate_weights(self, signal_df: pd.DataFrame, prices: pd.DataFrame | None = None) -> pd.DataFrame:
        top_frac = float(self.params.get("top_frac", 0.3))
        bottom_frac = float(self.params.get("bottom_frac", 0.3))

        ranks = signal_df.rank(axis=1, pct=True, na_option="keep")

        long_mask = ranks >= (1 - top_frac)
        short_mask = ranks <= bottom_frac

        long_score = (ranks - 0.5).where(long_mask, 0.0)
        short_score = (ranks - 0.5).where(short_mask, 0.0)  # negative

        long_gross = long_score.abs().sum(axis=1).replace(0.0, pd.NA)
        short_gross = short_score.abs().sum(axis=1).replace(0.0, pd.NA)

        long_weights = long_score.div(long_gross, axis=0).fillna(0.0) * 0.5
        short_weights = short_score.div(short_gross, axis=0).fillna(0.0) * 0.5

        return long_weights + short_weights
