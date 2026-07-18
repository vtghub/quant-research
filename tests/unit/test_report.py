from __future__ import annotations

import matplotlib.figure
import numpy as np
import pandas as pd
import pytest

from quant_research.backtest.costs import BpsCostModel
from quant_research.backtest.engine import BacktestEngine
from quant_research.config.schema import PipelineConfig
from quant_research.report.plots import decile_spread_bar, drawdown_plot, equity_curve_plot, ic_series_plot
from quant_research.report.tearsheet import generate_tearsheet
from quant_research.research.ic_analysis import run_ic_analysis


@pytest.fixture
def bt_result(synthetic_prices: pd.DataFrame):
    dates = synthetic_prices.index
    weights = pd.DataFrame(1.0 / synthetic_prices.shape[1], index=dates, columns=synthetic_prices.columns)
    engine = BacktestEngine(BpsCostModel(5.0), initial_capital=1_000_000.0)
    return engine.run(weights, synthetic_prices)


@pytest.fixture
def ic_result(synthetic_prices: pd.DataFrame):
    signal = synthetic_prices.rank(axis=1, pct=True)
    return run_ic_analysis(synthetic_prices, signal, horizons=[1, 5], n_quantiles=5)


def test_equity_curve_plot_returns_figure(bt_result) -> None:
    fig = equity_curve_plot(bt_result.equity_curve)
    assert isinstance(fig, matplotlib.figure.Figure)


def test_drawdown_plot_returns_figure(bt_result) -> None:
    fig = drawdown_plot(bt_result.equity_curve)
    assert isinstance(fig, matplotlib.figure.Figure)


def test_ic_series_plot_returns_figure(ic_result) -> None:
    fig = ic_series_plot(ic_result.ic_series)
    assert isinstance(fig, matplotlib.figure.Figure)


def test_decile_spread_bar_returns_figure(ic_result) -> None:
    fig = decile_spread_bar(ic_result.decile_spreads)
    assert isinstance(fig, matplotlib.figure.Figure)


@pytest.fixture
def config(tmp_path) -> PipelineConfig:
    return PipelineConfig(
        name="report_test",
        universe={
            "symbols": ["AAA", "BBB"],
            "start": "2020-01-01",
            "end": "2020-06-01",
            "primary_source": "yfinance",
        },
        signals=[{"name": "momentum", "alias": "mom"}],
        strategy={"name": "rank_weighted_long_short", "signals": ["mom"]},
        report={"output_dir": str(tmp_path / "reports"), "formats": ["markdown", "png"]},
    )


def test_generate_tearsheet_writes_markdown_and_pngs(bt_result, ic_result, config) -> None:
    paths = generate_tearsheet(bt_result, ic_result, config)

    assert len(paths) == 5  # 4 pngs + 1 markdown
    for path in paths:
        assert path.exists()

    md_path = next(p for p in paths if p.suffix == ".md")
    text = md_path.read_text()
    assert "Backtest Metrics" in text
    assert "IC Summary" in text
    assert "sharpe" in text
    assert "Not investment advice" in text


def test_generate_tearsheet_without_ic_result(bt_result, config) -> None:
    paths = generate_tearsheet(bt_result, None, config)
    md_path = next(p for p in paths if p.suffix == ".md")
    text = md_path.read_text()
    assert "IC Summary" not in text
    assert "Backtest Metrics" in text


def test_generate_tearsheet_markdown_only(bt_result, ic_result, tmp_path) -> None:
    config = PipelineConfig(
        name="md_only",
        universe={
            "symbols": ["AAA"],
            "start": "2020-01-01",
            "end": "2020-06-01",
            "primary_source": "yfinance",
        },
        signals=[{"name": "momentum", "alias": "mom"}],
        strategy={"name": "rank_weighted_long_short", "signals": ["mom"]},
        report={"output_dir": str(tmp_path / "reports2"), "formats": ["markdown"]},
    )
    paths = generate_tearsheet(bt_result, ic_result, config)
    assert len(paths) == 1
    assert paths[0].suffix == ".md"
