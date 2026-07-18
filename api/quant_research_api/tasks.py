from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from quant_research_api import bootstrap  # noqa: F401 -- side effect: registers all built-ins
from quant_research_api.celery_app import celery_app
from quant_research_api.database import SessionLocal
from quant_research_api.models import Run
from quant_research_api.settings import settings

from quant_research.config.schema import PipelineConfig
from quant_research.pipeline.orchestrator import Pipeline
from quant_research.pipeline.results import PipelineResult, ResearchResult


def _series_to_records(series: pd.Series) -> list[dict[str, Any]]:
    return [
        {
            "date": idx.isoformat() if hasattr(idx, "isoformat") else str(idx),
            "value": None if pd.isna(val) else float(val),
        }
        for idx, val in series.items()
    ]


def _clean_metrics(metrics: dict[str, float]) -> dict[str, float | None]:
    return {key: (float(value) if np.isfinite(value) else None) for key, value in metrics.items()}


def _summarize_research(result: ResearchResult) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "signals": {alias: list(df.columns) for alias, df in result.signals.items()},
        "price_symbols": list(result.prices.columns),
        "date_range": (
            [result.prices.index.min().isoformat(), result.prices.index.max().isoformat()]
            if not result.prices.empty
            else None
        ),
    }
    if result.ic_result is not None:
        summary["ic_summary"] = {
            str(horizon): {
                "mean_ic": summary_stat.mean_ic,
                "std_ic": summary_stat.std_ic,
                "ic_ir": summary_stat.ic_ir,
                "t_stat": summary_stat.t_stat,
                "hit_rate": summary_stat.hit_rate,
            }
            for horizon, summary_stat in result.ic_result.summaries.items()
        }
    return summary


def _summarize_backtest(result: PipelineResult) -> dict[str, Any]:
    summary = _summarize_research(result.research)
    summary["metrics"] = _clean_metrics(result.backtest.metrics)
    summary["equity_curve"] = _series_to_records(result.backtest.equity_curve)
    summary["report_paths"] = result.report_paths
    return summary


@celery_app.task(bind=True, name="quant_research_api.run_pipeline")
def run_pipeline_task(self, run_id: int) -> None:
    db = SessionLocal()
    try:
        run = db.get(Run, run_id)
        if run is None:
            return

        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        db.commit()

        try:
            config = PipelineConfig(**run.config_snapshot)
            # per-run artifact isolation: two runs must never overwrite each
            # other's tearsheet files, even if their source config shares a
            # report.output_dir (e.g. two runs of the same saved config).
            run_report_dir = Path(settings.artifacts_root) / str(run_id)
            config.report.output_dir = run_report_dir

            pipeline = Pipeline(config)
            if run.kind == "research":
                research_result = pipeline.run_research()
                run.result_json = _summarize_research(research_result)
            else:
                pipeline_result = pipeline.run_backtest()
                run.result_json = _summarize_backtest(pipeline_result)
                run.report_dir = str(run_report_dir)
            run.status = "success"
        except Exception as exc:  # noqa: BLE001 -- surfaced to the user via the API, never swallowed
            run.status = "failed"
            run.error_message = str(exc)

        run.finished_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()
