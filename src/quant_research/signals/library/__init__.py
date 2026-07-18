"""Importing this package registers every built-in signal into SIGNAL_REGISTRY.
Add a new signal by creating a module here and importing it below."""
from quant_research.signals.library import (  # noqa: F401
    bollinger,
    breakout,
    composite,
    cross_sectional_rank,
    macd,
    macro_overlay,
    mean_reversion,
    momentum,
    pairs_zscore,
    realized_vol,
    rsi,
    value_proxy,
)
