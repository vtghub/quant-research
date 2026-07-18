from __future__ import annotations

import pandas as pd

from quant_research.core.exceptions import ConfigError
from quant_research.core.registries import SIGNAL_REGISTRY
from quant_research.signals.base import Signal


@SIGNAL_REGISTRY.register("xs_rank")
class CrossSectionalRankSignal(Signal):
    """Meta-signal: percentile-ranks an upstream signal's output across the
    universe each day, mapped to [-1, 1]. Requires `depends_on` naming exactly
    one upstream signal alias (or set params.source explicitly)."""

    name = "xs_rank"

    def compute(self, prices: pd.DataFrame, inputs: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
        if not inputs:
            raise ConfigError("xs_rank requires depends_on naming an upstream signal alias")
        source_alias = self.params.get("source", next(iter(inputs)))
        if source_alias not in inputs:
            raise ConfigError(f"xs_rank params.source '{source_alias}' is not one of depends_on {list(inputs)}")
        base = inputs[source_alias]
        return base.rank(axis=1, pct=True) * 2 - 1
