from __future__ import annotations

from pathlib import Path

import typer

from quant_research.config.loader import load_config
from quant_research.core.exceptions import QuantResearchError
from quant_research.core.registries import (
    CACHE_BACKEND_REGISTRY,
    DATA_SOURCE_REGISTRY,
    MACRO_SOURCE_REGISTRY,
    SIGNAL_REGISTRY,
    STRATEGY_REGISTRY,
)
from quant_research.pipeline.orchestrator import Pipeline  # side-effect: registers all built-ins

app = typer.Typer(
    help="Modular, hook-driven engine for quantitative trading research on free data.",
    no_args_is_help=True,
)


@app.command()
def research(config: Path = typer.Argument(..., exists=True, help="Path to a pipeline YAML config")) -> None:
    """Fetch data, compute signals, run IC screening -- no strategy/backtest required."""
    try:
        cfg = load_config(config)
        result = Pipeline(cfg).run_research()
    except QuantResearchError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Fetched prices: {result.prices.shape[0]} dates x {result.prices.shape[1]} symbols")
    for alias, frame in result.signals.items():
        typer.echo(f"  signal '{alias}': {frame.shape}")
    if result.ic_result is not None:
        typer.echo("IC summary:")
        for horizon, summary in sorted(result.ic_result.summaries.items()):
            typer.echo(
                f"  [{horizon}d] mean_ic={summary.mean_ic:.4f} ic_ir={summary.ic_ir:.4f} "
                f"t_stat={summary.t_stat:.2f} hit_rate={summary.hit_rate:.2%}"
            )


@app.command()
def backtest(config: Path = typer.Argument(..., exists=True, help="Path to a pipeline YAML config")) -> None:
    """Full pipeline: research -> strategy -> backtest -> tearsheet report."""
    try:
        cfg = load_config(config)
        result = Pipeline(cfg).run_backtest()
    except QuantResearchError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Final equity: {result.backtest.equity_curve.iloc[-1]:,.2f}")
    for key, value in result.backtest.metrics.items():
        typer.echo(f"  {key}: {value:.4f}")
    if result.report_paths:
        typer.echo("Report written to:")
        for path in result.report_paths:
            typer.echo(f"  {path}")


@app.command(name="run")
def run(config: Path = typer.Argument(..., exists=True, help="Path to a pipeline YAML config")) -> None:
    """Alias for `backtest` -- runs the full pipeline end to end."""
    backtest(config)


@app.command(name="list-registry")
def list_registry() -> None:
    """Dump every registered data source / signal / strategy, for config authors."""
    typer.echo("Data sources:   " + ", ".join(DATA_SOURCE_REGISTRY.list()))
    typer.echo("Macro sources:  " + ", ".join(MACRO_SOURCE_REGISTRY.list()))
    typer.echo("Cache backends: " + ", ".join(CACHE_BACKEND_REGISTRY.list()))
    typer.echo("Signals:        " + ", ".join(SIGNAL_REGISTRY.list()))
    typer.echo("Strategies:     " + ", ".join(STRATEGY_REGISTRY.list()))


@app.command(name="validate-config")
def validate_config(config: Path = typer.Argument(..., exists=True, help="Path to a pipeline YAML config")) -> None:
    """Validate a config file without fetching data or running anything."""
    try:
        cfg = load_config(config)
    except QuantResearchError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"OK: '{cfg.name}' is valid.", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
