from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from quant_research.backtest.engine import BacktestResult
from quant_research.research.ic_analysis import ICAnalysisResult


@dataclass
class ResearchResult:
    prices: pd.DataFrame  # wide date x symbol
    signals: dict[str, pd.DataFrame]  # alias -> wide date x symbol
    ic_result: ICAnalysisResult | None = None


@dataclass
class PipelineResult:
    research: ResearchResult
    backtest: BacktestResult
    report_paths: list[str] | None = None
