from __future__ import annotations

import pandas as pd

from quant_research.config.schema import SignalConfig
from quant_research.core.exceptions import ConfigError
from quant_research.core.hooks import HookEvent, HookManager
from quant_research.core.registries import SIGNAL_REGISTRY


def compute_signals(
    prices: pd.DataFrame,
    configs: list[SignalConfig],
    hooks: HookManager | None = None,
) -> dict[str, pd.DataFrame]:
    """Compute every configured signal, resolving depends_on in topological order
    so meta-signals (cross-sectional rank, composite, macro overlay) can consume
    other signals' outputs by alias."""
    hooks = hooks or HookManager()
    by_alias = {cfg.resolved_alias: cfg for cfg in configs}
    results: dict[str, pd.DataFrame] = {}
    resolving: set[str] = set()

    def resolve(alias: str) -> pd.DataFrame:
        if alias in results:
            return results[alias]
        if alias in resolving:
            raise ConfigError(f"circular signal dependency involving '{alias}'")
        if alias not in by_alias:
            raise ConfigError(f"signal alias '{alias}' is not configured")

        cfg = by_alias[alias]
        resolving.add(alias)
        try:
            inputs = {dep: resolve(dep) for dep in cfg.depends_on}
        finally:
            resolving.discard(alias)

        hooks.fire(HookEvent.BEFORE_SIGNAL, alias=alias, name=cfg.name, params=cfg.params)
        signal = SIGNAL_REGISTRY.create(cfg.name, **cfg.params)
        result = signal.compute(prices, inputs or None)
        hooks.fire(HookEvent.AFTER_SIGNAL, alias=alias, name=cfg.name, df=result)

        results[alias] = result
        return result

    for alias in by_alias:
        resolve(alias)
    return results
