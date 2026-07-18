from __future__ import annotations

from fastapi import APIRouter

from quant_research_api import bootstrap  # noqa: F401 -- side effect: registers all built-ins

from quant_research.core.registries import (
    CACHE_BACKEND_REGISTRY,
    DATA_SOURCE_REGISTRY,
    FUNDAMENTALS_SOURCE_REGISTRY,
    MACRO_SOURCE_REGISTRY,
    SIGNAL_REGISTRY,
    STRATEGY_REGISTRY,
    UNIVERSE_PROVIDER_REGISTRY,
)
from quant_research_api.schemas import RegistryOut

router = APIRouter(prefix="/registry", tags=["registry"])


@router.get("", response_model=RegistryOut)
def get_registry() -> RegistryOut:
    """Everything a frontend config-builder form needs to populate its
    dropdowns -- the same registries the CLI's `list-registry` command reads."""
    return RegistryOut(
        data_sources=DATA_SOURCE_REGISTRY.list(),
        macro_sources=MACRO_SOURCE_REGISTRY.list(),
        fundamentals_sources=FUNDAMENTALS_SOURCE_REGISTRY.list(),
        cache_backends=CACHE_BACKEND_REGISTRY.list(),
        universe_providers=UNIVERSE_PROVIDER_REGISTRY.list(),
        signals=SIGNAL_REGISTRY.list(),
        strategies=STRATEGY_REGISTRY.list(),
    )
