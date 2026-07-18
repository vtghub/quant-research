"""Assembles the full pipeline (fetch -> cache -> signals -> strategy -> backtest)
from a validated PipelineConfig, resolving every swappable piece through the
registries by the names given in config."""
from __future__ import annotations

import importlib

# Side-effect imports: importing these packages registers every built-in
# implementation (data sources, cache backends, signals, strategies) into the
# core registries before Pipeline ever resolves anything by name.
import quant_research.cache.parquet_backend  # noqa: F401
import quant_research.data.sources  # noqa: F401
import quant_research.signals.library  # noqa: F401
import quant_research.strategy.library  # noqa: F401
from quant_research.backtest.costs import BpsCostModel
from quant_research.backtest.engine import BacktestEngine
from quant_research.config.schema import PipelineConfig
from quant_research.core.hooks import HookEvent, HookManager
from quant_research.core.registries import CACHE_BACKEND_REGISTRY, DATA_SOURCE_REGISTRY, STRATEGY_REGISTRY
from quant_research.data.access import DataAccessLayer
from quant_research.pipeline.results import PipelineResult, ResearchResult
from quant_research.signals.pipeline import compute_signals


class Pipeline:
    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.hooks = HookManager()
        for module_path in config.hooks.modules:
            module = importlib.import_module(module_path)
            module.register(self.hooks)

        self.cache = CACHE_BACKEND_REGISTRY.create(
            config.cache.backend, root_dir=config.cache.root_dir, **config.cache.params
        )
        self.data_access = DataAccessLayer(self.cache, self.hooks)

    def _load_prices(self):
        universe = self.config.universe
        source = DATA_SOURCE_REGISTRY.create(universe.primary_source)
        long_df = self.data_access.get_ohlcv_long(
            source, universe.symbols, universe.start, universe.end, universe.interval
        )
        return DataAccessLayer.to_wide(long_df, price_field=universe.price_field)

    def run_research(self) -> ResearchResult:
        prices = self._load_prices()
        signals = compute_signals(prices, self.config.signals, self.hooks)
        return ResearchResult(prices=prices, signals=signals)

    def run_backtest(self) -> PipelineResult:
        research = self.run_research()

        self.hooks.fire(HookEvent.BEFORE_BACKTEST, config=self.config.backtest)

        strategy = STRATEGY_REGISTRY.create(self.config.strategy.name, **self.config.strategy.params)
        primary_alias = self.config.strategy.signals[0]
        signal_df = research.signals[primary_alias]
        weights = strategy.generate_weights(signal_df, research.prices)

        engine = BacktestEngine(
            cost_model=BpsCostModel(self.config.backtest.cost_model.bps_per_trade),
            initial_capital=self.config.backtest.initial_capital,
        )
        bt_result = engine.run(weights, research.prices)

        self.hooks.fire(HookEvent.AFTER_BACKTEST, result=bt_result)

        return PipelineResult(research=research, backtest=bt_result)
