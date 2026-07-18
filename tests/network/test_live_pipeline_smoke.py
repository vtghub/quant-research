"""Live end-to-end smoke test -- excluded by default, run via `pytest -m
network`. Exercises the full pipeline (fetch -> cache -> signals -> IC ->
strategy -> backtest -> tearsheet) against real yfinance data, no API key
required. See tests/network/test_live_data_sources.py for why this can't run
in the local dev session."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quant_research.config.loader import load_config
from quant_research.pipeline.orchestrator import Pipeline

pytestmark = pytest.mark.network

CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "example_live_smoke.yaml"


@pytest.fixture
def config(tmp_path):
    cfg = load_config(CONFIG_PATH)
    # keep the live run fast and self-contained: isolate cache/report dirs to tmp_path
    cfg.cache.root_dir = tmp_path / "cache"
    cfg.report.output_dir = tmp_path / "reports"
    return cfg


def test_live_research_produces_real_prices_and_ic(config) -> None:
    pipeline = Pipeline(config)
    research = pipeline.run_research()

    assert not research.prices.empty
    assert set(research.prices.columns) == {"SPY", "QQQ", "TLT"}
    assert research.prices.notna().any().any()

    assert research.ic_result is not None
    for horizon, summary in research.ic_result.summaries.items():
        assert np.isfinite(summary.mean_ic)


def test_live_backtest_produces_real_tearsheet(config) -> None:
    pipeline = Pipeline(config)
    result = pipeline.run_backtest()

    assert not result.backtest.equity_curve.empty
    for value in result.backtest.metrics.values():
        assert np.isfinite(value)

    assert result.report_paths
    for path_str in result.report_paths:
        assert Path(path_str).exists()

    tearsheet_path = next(p for p in result.report_paths if p.endswith(".md"))
    text = Path(tearsheet_path).read_text()
    assert "example_live_smoke" in text
    assert "Backtest Metrics" in text
