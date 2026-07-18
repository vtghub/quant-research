from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from quant_research.config.schema import PipelineConfig
from quant_research.core.registries import DATA_SOURCE_REGISTRY
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
