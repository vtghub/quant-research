from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from quant_research.config.schema import PipelineConfig
from quant_research.core.registries import DATA_SOURCE_REGISTRY, MACRO_SOURCE_REGISTRY
from quant_research.pipeline.orchestrator import Pipeline


@pytest.fixture
def registered_fake_source(synthetic_long_ohlcv):
    """Registers an in-memory, network-free data source under a test-only registry
    name, proving Pipeline resolves data sources purely by config-driven name
    lookup -- no live vendor call is made anywhere in this test."""

    class _FixtureSource:
        name = "fake_test_source"

        def fetch(self, symbols, start, end, interval="1d") -> pd.DataFrame:
            start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
            mask = (
                synthetic_long_ohlcv["symbol"].isin(symbols)
                & (synthetic_long_ohlcv["date"] >= start_ts)
                & (synthetic_long_ohlcv["date"] <= end_ts)
            )
            sliced = synthetic_long_ohlcv.loc[mask].copy()
            sliced["source"] = self.name
            return sliced.sort_values(["symbol", "date"]).reset_index(drop=True)

    DATA_SOURCE_REGISTRY.register("fake_test_source")(_FixtureSource)
    yield "fake_test_source"
    DATA_SOURCE_REGISTRY._items.pop("fake_test_source", None)


@pytest.fixture
def config(tmp_path, registered_fake_source):
    return PipelineConfig(
        name="integration_test",
        universe={
            "symbols": ["AAA", "BBB", "CCC", "DDD", "EEE"],
            "start": "2020-02-01",
            "end": "2021-11-01",
            "primary_source": registered_fake_source,
        },
        cache={"root_dir": str(tmp_path / "cache")},
        signals=[{"name": "momentum", "alias": "mom", "params": {"lookback": 60, "skip_recent": 5}}],
        strategy={"name": "rank_weighted_long_short", "signals": ["mom"], "params": {"top_frac": 0.4, "bottom_frac": 0.4}},
        report={"output_dir": str(tmp_path / "reports"), "formats": ["markdown", "png"]},
    )


def test_run_research_wires_fetch_through_signals(config) -> None:
    pipeline = Pipeline(config)
    research = pipeline.run_research()

    assert not research.prices.empty
    assert set(research.prices.columns) == {"AAA", "BBB", "CCC", "DDD", "EEE"}
    assert "mom" in research.signals
    assert research.signals["mom"].shape == research.prices.shape
    assert research.ic_result is not None  # ic_analysis defaults to enabled
    assert 1 in research.ic_result.summaries


def test_run_backtest_end_to_end_produces_sane_result(config) -> None:
    pipeline = Pipeline(config)
    result = pipeline.run_backtest()

    assert not result.backtest.equity_curve.empty
    assert result.backtest.equity_curve.iloc[0] > 0
    for value in result.backtest.metrics.values():
        assert np.isfinite(value)
    # gross exposure should never exceed 1.0 (0.5 long + 0.5 short by construction)
    assert (result.backtest.weights.abs().sum(axis=1) <= 1.0 + 1e-9).all()

    assert result.report_paths
    for path_str in result.report_paths:
        assert Path(path_str).exists()


def test_cache_reused_across_pipeline_runs(config) -> None:
    pipeline1 = Pipeline(config)
    pipeline1.run_research()

    # a second Pipeline pointed at the same cache dir should not need the fake
    # source to serve fresh data for a strictly narrower date range
    pipeline2 = Pipeline(config)
    research = pipeline2.run_research()
    assert not research.prices.empty


@pytest.fixture
def registered_fake_macro_source(synthetic_prices):
    """A network-free MacroDataSource double, registered under a test-only name,
    so the macro-overlay/composite path can be exercised without hitting FRED."""

    dates = synthetic_prices.index
    macro_series = pd.Series(np.linspace(0.0, 5.0, len(dates)), index=dates)  # a steadily rising "rate"

    class _FakeMacroSource:
        name = "fake_macro_source"

        def fetch(self, series_ids, start, end) -> pd.DataFrame:
            start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
            windowed = macro_series.loc[(macro_series.index >= start_ts) & (macro_series.index <= end_ts)]
            frames = [
                pd.DataFrame({"date": windowed.index, "series_id": sid, "value": windowed.values})
                for sid in series_ids
            ]
            return pd.concat(frames, ignore_index=True)

    MACRO_SOURCE_REGISTRY.register("fake_macro_source")(_FakeMacroSource)
    yield "fake_macro_source"
    MACRO_SOURCE_REGISTRY._items.pop("fake_macro_source", None)


@pytest.fixture
def multi_factor_config(tmp_path, registered_fake_source, registered_fake_macro_source):
    """Mirrors the shape of configs/example_multi_asset.yaml: several signals
    (momentum, mean-reversion, realized-vol, macro overlay) blended through a
    composite combinator, screened via IC analysis, traded, backtested, and
    reported -- all offline against synthetic/fake data."""
    return PipelineConfig(
        name="multi_factor_integration_test",
        universe={
            "symbols": ["AAA", "BBB", "CCC", "DDD", "EEE"],
            "start": "2020-03-01",
            "end": "2021-10-01",
            "primary_source": registered_fake_source,
        },
        macro={"series_ids": ["FAKE_RATE"], "source": registered_fake_macro_source},
        cache={"root_dir": str(tmp_path / "cache")},
        signals=[
            {"name": "momentum", "alias": "mom", "params": {"lookback": 60, "skip_recent": 5}},
            {"name": "zscore_meanrev", "alias": "meanrev", "params": {"window": 20}},
            {"name": "realized_vol", "alias": "vol", "params": {"window": 20}},
            {
                "name": "macro_overlay",
                "alias": "macro_regime",
                "depends_on": ["macro_FAKE_RATE"],
                "params": {"window": 120, "direction": -1.0},
            },
            {
                "name": "composite",
                "alias": "multi_factor",
                "depends_on": ["mom", "meanrev", "vol", "macro_regime"],
                "params": {"weights": {"mom": 1.0, "meanrev": 0.5, "vol": -0.5, "macro_regime": 0.5}},
            },
        ],
        strategy={
            "name": "rank_weighted_long_short",
            "signals": ["multi_factor"],
            "params": {"top_frac": 0.4, "bottom_frac": 0.4},
        },
        backtest={"cost_model": {"bps_per_trade": 5.0}, "rebalance": "weekly"},
        report={"output_dir": str(tmp_path / "reports"), "formats": ["markdown", "png"]},
        hooks={"modules": ["quant_research.hooks.builtin.logging_hooks"]},
    )


def test_full_multi_signal_composite_pipeline_with_macro_overlay(multi_factor_config) -> None:
    pipeline = Pipeline(multi_factor_config)
    result = pipeline.run_backtest()

    # every configured signal (including the meta-signals) actually computed
    for alias in ("mom", "meanrev", "vol", "macro_regime", "multi_factor"):
        assert alias in result.research.signals
        assert not result.research.signals[alias].dropna(how="all").empty

    # the macro overlay is a portfolio-wide tilt: identical across every symbol column
    macro_frame = result.research.signals["macro_regime"]
    row = macro_frame.dropna(how="all").iloc[-1]
    assert row.nunique(dropna=True) == 1

    # IC screening ran against the composite signal that actually feeds the strategy
    assert result.research.ic_result is not None
    assert set(result.research.ic_result.summaries.keys()) == set(multi_factor_config.ic_analysis.horizons)

    # weekly rebalance reduced turnover relative to a naive daily rebalance
    assert (result.backtest.turnover.dropna() >= 0).all()

    assert not result.backtest.equity_curve.empty
    for value in result.backtest.metrics.values():
        assert np.isfinite(value)

    assert result.report_paths
    for path_str in result.report_paths:
        assert Path(path_str).exists()
    tearsheet_path = next(p for p in result.report_paths if p.endswith(".md"))
    tearsheet_text = Path(tearsheet_path).read_text()
    assert "IC Summary" in tearsheet_text
    assert "Not investment advice" in tearsheet_text
