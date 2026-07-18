from __future__ import annotations

import pandas as pd

from quant_research.core.exceptions import ConfigError
from quant_research.core.registries import SIGNAL_REGISTRY
from quant_research.signals.base import Signal


@SIGNAL_REGISTRY.register("value_proxy")
class ValueProxySignal(Signal):
    """Value/quality proxy: ratio of a fundamentals concept (already pivoted to
    a wide date x symbol frame via depends_on, e.g.
    'fundamentals_EarningsPerShareBasic') to price -- e.g. EPS/price = earnings
    yield. Higher ratio = more "value" by default (params.direction=1.0); set
    direction=-1.0 to flip for a concept where a higher ratio should score
    negatively (e.g. a debt-like figure)."""

    name = "value_proxy"

    def compute(self, prices: pd.DataFrame, inputs: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
        if not inputs:
            raise ConfigError("value_proxy requires depends_on naming a fundamentals input alias")
        source_alias = self.params.get("source", next(iter(inputs)))
        if source_alias not in inputs:
            raise ConfigError(f"value_proxy params.source '{source_alias}' is not one of depends_on {list(inputs)}")

        fundamentals_wide = inputs[source_alias]
        direction = float(self.params.get("direction", 1.0))
        return (fundamentals_wide / prices) * direction
