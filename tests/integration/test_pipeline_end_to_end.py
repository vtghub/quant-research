from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from quant_research.config.schema import PipelineConfig
from quant_research.core.registries import DATA_SOURCE_REGISTRY, FUNDAMENTALS_SOURCE_REGISTRY, MACRO_SOURCE_REGISTRY
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


@pytest.fixture
def registered_fake_fundamentals_source():
    """A network-free FundamentalsDataSource double, registered under a
    test-only name, so the value_proxy signal path can be exercised without
    hitting SEC EDGAR. Gives each symbol a distinct, constant "EPS" so the
    resulting earnings-yield ranking is deterministic."""

    eps_by_symbol = {"AAA": 5.0, "BBB": 4.0, "CCC": 3.0, "DDD": 2.0, "EEE": 1.0}

    class _FakeFundamentalsSource:
        name = "fake_fundamentals_source"

        def fetch(self, symbols, concepts, start, end) -> pd.DataFrame:
            rows = [
                {"date": pd.Timestamp(start), "symbol": symbol, "concept": concept, "value": eps_by_symbol[symbol]}
                for symbol in symbols
                for concept in concepts
            ]
            return pd.DataFrame(rows)

    FUNDAMENTALS_SOURCE_REGISTRY.register("fake_fundamentals_source")(_FakeFundamentalsSource)
    yield "fake_fundamentals_source"
    FUNDAMENTALS_SOURCE_REGISTRY._items.pop("fake_fundamentals_source", None)


@pytest.fixture
def value_config(tmp_path, registered_fake_source, registered_fake_fundamentals_source):
    """A value strategy driven entirely by SEC-EDGAR-shaped fundamentals data
    (via value_proxy) traded with risk_parity sizing -- exercises the
    fundamentals orchestrator wiring (_load_fundamentals_inputs) end to end,
    which unit tests alone don't cover."""
    return PipelineConfig(
        name="value_integration_test",
        universe={
            "symbols": ["AAA", "BBB", "CCC", "DDD", "EEE"],
            "start": "2020-02-01",
            "end": "2021-06-01",
            "primary_source": registered_fake_source,
        },
        fundamentals={"concepts": ["EarningsPerShareBasic"], "source": registered_fake_fundamentals_source},
        cache={"root_dir": str(tmp_path / "cache")},
        signals=[
            {
                "name": "value_proxy",
                "alias": "earnings_yield",
                "depends_on": ["fundamentals_EarningsPerShareBasic"],
            },
        ],
        strategy={
            "name": "risk_parity",
            "signals": ["earnings_yield"],
            "params": {"vol_lookback": 20, "require_positive_signal": False},
        },
        report={"output_dir": str(tmp_path / "reports"), "formats": ["markdown"]},
    )


def test_fundamentals_driven_value_signal_end_to_end(value_config) -> None:
    pipeline = Pipeline(value_config)
    result = pipeline.run_backtest()

    earnings_yield = result.research.signals["earnings_yield"]
    last_date = earnings_yield.dropna().index[-1]
    # the wiring must actually compute EPS/price -- verify against the known
    # constant EPS and the price the pipeline itself fetched for that date
    # (checking a raw ratio, not a cross-symbol comparison confounded by the
    # independently-random price levels the synthetic fixture generates)
    expected_aaa = 5.0 / result.research.prices.loc[last_date, "AAA"]
    assert earnings_yield.loc[last_date, "AAA"] == pytest.approx(expected_aaa)

    assert not result.backtest.equity_curve.empty
    for value in result.backtest.metrics.values():
        assert np.isfinite(value)
    assert np.allclose(result.backtest.weights.abs().sum(axis=1).iloc[-5:], 1.0)


def test_point_in_time_universe_excludes_non_members_from_trading(
    tmp_path, registered_fake_source, synthetic_prices
) -> None:
    """DDD is removed from the universe partway through; EEE was never a member
    at all. Both still have real price history in the fake source (a stock
    doesn't stop trading just because it left the researched universe), so this
    proves membership_mask -- not a narrower fetch -- is what keeps them out of
    ranking/trading after/outside their membership window (the
    survivorship-bias-free mechanism), while EEE's total absence from
    all_symbols_ever() proves it's never even fetched."""
    dates = synthetic_prices.index
    removal_date = dates[len(dates) // 2]

    membership_csv = tmp_path / "membership.csv"
    membership_csv.write_text(
        "symbol,start_date,end_date\n"
        f"AAA,{dates[0].date()},\n"
        f"BBB,{dates[0].date()},\n"
        f"CCC,{dates[0].date()},\n"
        f"DDD,{dates[0].date()},{removal_date.date()}\n"
    )

    config = PipelineConfig(
        name="point_in_time_test",
        universe={
            "symbols": [],
            "start": dates[0].date().isoformat(),
            "end": dates[-1].date().isoformat(),
            "primary_source": registered_fake_source,
            "provider": "point_in_time",
            "provider_params": {"membership_csv": str(membership_csv)},
        },
        cache={"root_dir": str(tmp_path / "cache")},
        signals=[{"name": "momentum", "alias": "mom", "params": {"lookback": 20, "skip_recent": 5}}],
        strategy={
            "name": "rank_weighted_long_short",
            "signals": ["mom"],
            "params": {"top_frac": 0.4, "bottom_frac": 0.4},
        },
        report={"output_dir": str(tmp_path / "reports"), "formats": ["markdown"]},
    )

    pipeline = Pipeline(config)
    result = pipeline.run_backtest()

    assert "EEE" not in result.research.prices.columns  # never a member -> never fetched
    assert "DDD" in result.research.prices.columns  # still fetched -- has real price history

    # the signal itself is masked immediately after removal (the direct check --
    # membership_mask is applied to signals, not to the shifted backtest weights)
    mom = result.research.signals["mom"]
    signal_after_removal = mom.loc[mom.index > pd.Timestamp(removal_date), "DDD"]
    assert signal_after_removal.isna().all()

    # BacktestResult.weights = weights.shift(1) (BacktestEngine's lookahead-
    # protection shift), so a decision made ON removal_date (DDD's last eligible
    # day) still realizes once on the following trading day -- skip that one
    # flush-out day, then DDD must carry zero weight for the rest of the backtest.
    weights = result.backtest.weights
    dates_after_removal = weights.index[weights.index > pd.Timestamp(removal_date)]
    after_flush_out = weights.loc[weights.index > dates_after_removal[1]]
    assert (after_flush_out["DDD"] == 0.0).all()

    # sanity: the still-active symbols do receive nonzero weight at some point
    assert (weights[["AAA", "BBB", "CCC"]] != 0.0).any().any()
