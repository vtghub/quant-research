"""Importing this package registers every built-in strategy into STRATEGY_REGISTRY.
Add a new strategy by creating a module here and importing it below."""
from quant_research.strategy import vol_target  # noqa: F401 (registers "vol_targeted")
from quant_research.strategy.library import rank_weighted, top_bottom_decile  # noqa: F401
