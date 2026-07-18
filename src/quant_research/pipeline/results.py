from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from quant_research.backtest.engine import BacktestResult


@dataclass
class ResearchResult:
    prices: pd.DataFrame  # wide date x symbol
    signals: dict[str, pd.DataFrame]  # alias -> wide date x symbol
    ic_result: object | None = None  # narrowed to ICAnalysisResult once research/ic_analysis exists (Stage B)


@dataclass
class PipelineResult:
    research: ResearchResult
    backtest: BacktestResult
    report_paths: list[str] | None = None
