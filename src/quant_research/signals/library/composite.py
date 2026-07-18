from __future__ import annotations

import numpy as np
import pandas as pd

from quant_research.core.exceptions import ConfigError
from quant_research.core.registries import SIGNAL_REGISTRY
from quant_research.signals.base import Signal


@SIGNAL_REGISTRY.register("composite")
class CompositeSignal(Signal):
    """Blends multiple upstream signals into one multi-factor score: each input is
    cross-sectionally z-scored per date (so signals on different scales are
    comparable), scaled by `params.weights[alias]` (default 1.0 for any input not
    listed), and averaged by total absolute weight. `depends_on` must name every
    signal alias to combine -- this is what turns several signals computed side by
    side into an actual multi-factor strategy input."""

    name = "composite"

    def compute(self, prices: pd.DataFrame, inputs: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
        if not inputs:
            raise ConfigError("composite requires depends_on naming at least one upstream signal alias")

        weights: dict[str, float] = self.params.get("weights", {})
        default_weight = 1.0

        weighted_frames = []
        total_weight = 0.0
        for alias, frame in inputs.items():
            w = float(weights.get(alias, default_weight))
            row_mean = frame.mean(axis=1)
            row_std = frame.std(axis=1, ddof=0).replace(0.0, np.nan)
            z = frame.sub(row_mean, axis=0).div(row_std, axis=0)
            weighted_frames.append(z * w)
            total_weight += abs(w)

        combined = weighted_frames[0]
        for frame in weighted_frames[1:]:
            combined = combined + frame

        if total_weight > 0:
            combined = combined / total_weight
        return combined
