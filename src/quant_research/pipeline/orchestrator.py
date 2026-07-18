"""Assembles the full pipeline (fetch -> cache -> signals -> IC analysis ->
strategy -> backtest -> report) from a validated PipelineConfig, resolving every
swappable piece through the registries by the names given in config."""
from __future__ import annotations

import importlib

# Side-effect imports: importing these packages registers every built-in
# implementation (data sources, cache backends, signals, strategies) into the
# core registries before Pipeline ever resolves anything by name.
import quant_research.cache.duckdb_backend  # noqa: F401
import quant_research.cache.parquet_backend  # noqa: F401
import quant_research.data.sources  # noqa: F401
import quant_research.signals.library  # noqa: F401
import quant_research.strategy.library  # noqa: F401
import pandas as pd

from quant_research.backtest.costs import BpsCostModel
from quant_research.backtest.engine import BacktestEngine
from quant_research.backtest.rebalance import apply_rebalance_schedule
from quant_research.config.schema import PipelineConfig
from quant_research.core.hooks import HookEvent, HookManager
from quant_research.core.registries import (
    CACHE_BACKEND_REGISTRY,
    DATA_SOURCE_REGISTRY,
    FUNDAMENTALS_SOURCE_REGISTRY,
    MACRO_SOURCE_REGISTRY,
    STRATEGY_REGISTRY,
)
from quant_research.data.access import DataAccessLayer
from quant_research.pipeline.results import PipelineResult, ResearchResult
from quant_research.report.tearsheet import generate_tearsheet
from quant_research.research.ic_analysis import run_ic_analysis
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

    def _load_prices(self) -> pd.DataFrame:
        universe = self.config.universe
        source = DATA_SOURCE_REGISTRY.create(universe.primary_source)
        long_df = self.data_access.get_ohlcv_long(
            source, universe.symbols, universe.start, universe.end, universe.interval
        )
        return DataAccessLayer.to_wide(long_df, price_field=universe.price_field)

    def _load_macro_inputs(self, calendar_index: pd.DatetimeIndex) -> dict[str, pd.DataFrame]:
        """Fetches each configured macro series and broadcasts it onto the price
        calendar under alias 'macro_<series_id>', so any signal's depends_on can
        reference it (see signals/library/macro_overlay.py)."""
        if not self.config.macro.series_ids:
            return {}

        macro_source = MACRO_SOURCE_REGISTRY.create(self.config.macro.source)
        macro_long = macro_source.fetch(
            self.config.macro.series_ids, self.config.universe.start, self.config.universe.end
        )

        extra_inputs = {}
        for series_id in self.config.macro.series_ids:
            alias = f"macro_{series_id}"
            extra_inputs[alias] = DataAccessLayer.broadcast_macro(
                macro_long, series_id, calendar_index, self.config.universe.symbols
            )
        return extra_inputs

    def _load_fundamentals_inputs(self, calendar_index: pd.DatetimeIndex) -> dict[str, pd.DataFrame]:
        """Fetches each configured fundamentals concept for the universe (or an
        explicit fundamentals.symbols override) and pivots it to a wide date x
        symbol frame under alias 'fundamentals_<concept>', forward-filled onto
        the price calendar (filings are quarterly at best)."""
        if not self.config.fundamentals.concepts:
            return {}

        symbols = self.config.fundamentals.symbols or self.config.universe.symbols
        fundamentals_source = FUNDAMENTALS_SOURCE_REGISTRY.create(self.config.fundamentals.source)
        fundamentals_long = fundamentals_source.fetch(
            symbols, self.config.fundamentals.concepts, self.config.universe.start, self.config.universe.end
        )

        extra_inputs = {}
        for concept in self.config.fundamentals.concepts:
            alias = f"fundamentals_{concept}"
            extra_inputs[alias] = DataAccessLayer.fundamentals_to_wide(
                fundamentals_long, concept, calendar_index, self.config.universe.symbols
            )
        return extra_inputs

    def run_research(self) -> ResearchResult:
        prices = self._load_prices()
        extra_inputs = self._load_macro_inputs(prices.index)
        extra_inputs.update(self._load_fundamentals_inputs(prices.index))
        signals = compute_signals(prices, self.config.signals, self.hooks, extra_inputs=extra_inputs)

        ic_result = None
        if self.config.ic_analysis.enabled and self.config.strategy.signals:
            primary_alias = self.config.strategy.signals[0]
            ic_result = run_ic_analysis(
                prices,
                signals[primary_alias],
                self.config.ic_analysis.horizons,
                self.config.ic_analysis.n_quantiles,
            )

        return ResearchResult(prices=prices, signals=signals, ic_result=ic_result)

    def run_backtest(self) -> PipelineResult:
        research = self.run_research()

        self.hooks.fire(HookEvent.BEFORE_BACKTEST, config=self.config.backtest)

        strategy = STRATEGY_REGISTRY.create(self.config.strategy.name, **self.config.strategy.params)
        primary_alias = self.config.strategy.signals[0]
        signal_df = research.signals[primary_alias]
        weights = strategy.generate_weights(signal_df, research.prices)
        weights = apply_rebalance_schedule(weights, self.config.backtest.rebalance)

        engine = BacktestEngine(
            cost_model=BpsCostModel(self.config.backtest.cost_model.bps_per_trade),
            initial_capital=self.config.backtest.initial_capital,
        )
        bt_result = engine.run(weights, research.prices)

        self.hooks.fire(HookEvent.AFTER_BACKTEST, result=bt_result)

        self.hooks.fire(HookEvent.BEFORE_REPORT, config=self.config.report)
        report_paths = generate_tearsheet(bt_result, research.ic_result, self.config)
        self.hooks.fire(HookEvent.AFTER_REPORT, paths=report_paths)

        return PipelineResult(
            research=research,
            backtest=bt_result,
            report_paths=[str(p) for p in report_paths],
        )
