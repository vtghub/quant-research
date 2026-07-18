from __future__ import annotations

import numpy as np
import pandas as pd

from quant_research.core.exceptions import ConfigError
from quant_research.core.registries import SIGNAL_REGISTRY
from quant_research.signals.base import Signal


@SIGNAL_REGISTRY.register("pairs_zscore")
class PairsZScoreSignal(Signal):
    """Stat-arb pairs signal: for each configured (symbol_a, symbol_b) pair,
    computes a rolling z-score of the log-price spread and assigns -z to
    symbol_a / +z to symbol_b -- when the spread is stretched (z far from 0),
    short the rich leg and long the cheap leg. Symbols not part of any
    configured pair get NaN (no signal, excluded from ranking downstream).
    params.pairs is required: a list of [symbol_a, symbol_b] pairs."""

    name = "pairs_zscore"

    def compute(self, prices: pd.DataFrame, inputs: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
        pairs = self.params.get("pairs")
        if not pairs:
            raise ConfigError("pairs_zscore requires params.pairs: a list of [symbol_a, symbol_b] pairs")
        window = int(self.params.get("window", 60))

        out = pd.DataFrame(np.nan, index=prices.index, columns=prices.columns)
        log_prices = np.log(prices)

        for symbol_a, symbol_b in pairs:
            if symbol_a not in prices.columns or symbol_b not in prices.columns:
                raise ConfigError(
                    f"pairs_zscore: pair ({symbol_a}, {symbol_b}) references a symbol not in the universe"
                )
            spread = log_prices[symbol_a] - log_prices[symbol_b]
            rolling_mean = spread.rolling(window).mean()
            rolling_std = spread.rolling(window).std(ddof=0)
            z = (spread - rolling_mean) / rolling_std

            out[symbol_a] = -z
            out[symbol_b] = z

        return out
