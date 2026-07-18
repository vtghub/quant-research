from __future__ import annotations

import pandas as pd

from quant_research.core.exceptions import ConfigError
from quant_research.core.registries import SIGNAL_REGISTRY
from quant_research.signals.base import Signal


@SIGNAL_REGISTRY.register("macro_overlay")
class MacroOverlaySignal(Signal):
    """Meta-signal: turns a market-wide macro series (already broadcast to every
    symbol column by the pipeline -- see data/access.py::broadcast_macro) into a
    rolling z-score regime score, applied uniformly across the universe as a
    portfolio-level tilt rather than a per-symbol ranking signal. `depends_on`
    must name the broadcast macro input alias; `params.direction` (default +1)
    flips the sign if a rising series should be read as risk-off instead of
    risk-on."""

    name = "macro_overlay"

    def compute(self, prices: pd.DataFrame, inputs: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
        if not inputs:
            raise ConfigError("macro_overlay requires depends_on naming a broadcast macro input alias")
        source_alias = self.params.get("source", next(iter(inputs)))
        if source_alias not in inputs:
            raise ConfigError(
                f"macro_overlay params.source '{source_alias}' is not one of depends_on {list(inputs)}"
            )
        macro_wide = inputs[source_alias]

        window = int(self.params.get("window", 252))
        min_periods = max(5, window // 10)
        rolling_mean = macro_wide.rolling(window, min_periods=min_periods).mean()
        rolling_std = macro_wide.rolling(window, min_periods=min_periods).std(ddof=0)
        z = (macro_wide - rolling_mean) / rolling_std

        direction = float(self.params.get("direction", 1.0))
        return z * direction
