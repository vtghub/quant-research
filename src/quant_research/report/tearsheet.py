from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from quant_research.backtest.engine import BacktestResult
from quant_research.config.schema import PipelineConfig
from quant_research.report.plots import decile_spread_bar, drawdown_plot, equity_curve_plot, ic_series_plot
from quant_research.research.ic_analysis import ICAnalysisResult

DISCLAIMER = (
    "**Limitations**: this run uses free data vendors with no guaranteed point-in-time "
    "index membership (survivorship-bias risk for broad universes), MVP calendar handling "
    "(crypto/macro series are forward-filled onto the equity/ETF trading calendar rather than "
    "modeled with full 24/7 precision), and cross-check sources (Stooq, CoinGecko) whose "
    "dividend/adjustment methodology may not match the primary source. Not investment advice."
)


def generate_tearsheet(
    bt_result: BacktestResult,
    ic_result: ICAnalysisResult | None,
    config: PipelineConfig,
) -> list[Path]:
    output_dir = Path(config.report.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    figure_names: list[str] = []

    if "png" in config.report.formats:
        figures = {
            "equity_curve": equity_curve_plot(bt_result.equity_curve),
            "drawdown": drawdown_plot(bt_result.equity_curve),
        }
        if ic_result is not None:
            figures["ic_series"] = ic_series_plot(ic_result.ic_series)
            figures["decile_spread"] = decile_spread_bar(ic_result.decile_spreads)

        for name, fig in figures.items():
            path = output_dir / f"{name}.png"
            fig.savefig(path, dpi=120)
            plt.close(fig)
            paths.append(path)
            figure_names.append(name)

    if "markdown" in config.report.formats:
        lines = [f"# {config.name} -- Tearsheet", ""]

        lines += ["## Backtest Metrics", "", "| Metric | Value |", "|---|---|"]
        for key, value in bt_result.metrics.items():
            lines.append(f"| {key} | {value:.4f} |")
        lines.append("")

        if ic_result is not None:
            lines += [
                "## IC Summary",
                "",
                "| Horizon | Mean IC | IC IR | t-stat | Hit Rate |",
                "|---|---|---|---|---|",
            ]
            for horizon, summary in sorted(ic_result.summaries.items()):
                lines.append(
                    f"| {horizon} | {summary.mean_ic:.4f} | {summary.ic_ir:.4f} | "
                    f"{summary.t_stat:.4f} | {summary.hit_rate:.2%} |"
                )
            lines.append("")

        if figure_names:
            lines.append("## Charts")
            lines.append("")
            for name in figure_names:
                lines.append(f"![{name}]({name}.png)")
            lines.append("")

        lines.append(DISCLAIMER)

        md_path = output_dir / "tearsheet.md"
        md_path.write_text("\n".join(lines))
        paths.append(md_path)

    return paths
