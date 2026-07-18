"""Central singleton registries. Implementation modules import the relevant registry
and register themselves via decorator at import time; nothing here imports those
implementation modules, avoiding import cycles.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from quant_research.core.registry import Registry

if TYPE_CHECKING:
    from quant_research.cache.base import CacheBackend
    from quant_research.data.base import MacroDataSource, OHLCVDataSource
    from quant_research.signals.base import Signal
    from quant_research.strategy.base import Strategy

CACHE_BACKEND_REGISTRY: Registry["CacheBackend"] = Registry("cache_backend")
DATA_SOURCE_REGISTRY: Registry["OHLCVDataSource"] = Registry("data_source")
MACRO_SOURCE_REGISTRY: Registry["MacroDataSource"] = Registry("macro_source")
SIGNAL_REGISTRY: Registry["Signal"] = Registry("signal")
STRATEGY_REGISTRY: Registry["Strategy"] = Registry("strategy")
