"""Importing this package registers every built-in strategy into STRATEGY_REGISTRY.
Add a new strategy by creating a module here and importing it below."""
from quant_research.strategy import vol_target  # noqa: F401 (registers "vol_targeted")
from quant_research.strategy.library import (  # noqa: F401
    min_variance,
    rank_weighted,
    risk_parity,
    top_bottom_decile,
)
