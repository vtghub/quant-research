from __future__ import annotations

import matplotlib.figure
import matplotlib.pyplot as plt
import pandas as pd


def equity_curve_plot(equity_curve: pd.Series) -> matplotlib.figure.Figure:
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(equity_curve.index, equity_curve.values)
    ax.set_title("Equity Curve")
    ax.set_xlabel("Date")
    ax.set_ylabel("Portfolio Value")
    fig.tight_layout()
    return fig


def drawdown_plot(equity_curve: pd.Series) -> matplotlib.figure.Figure:
    running_max = equity_curve.cummax()
    drawdown = equity_curve / running_max - 1.0
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.fill_between(drawdown.index, drawdown.values, 0, color="tab:red", alpha=0.5)
    ax.set_title("Drawdown")
    ax.set_ylabel("Drawdown")
    fig.tight_layout()
    return fig


def ic_series_plot(ic_by_horizon: dict[int, pd.Series]) -> matplotlib.figure.Figure:
    fig, ax = plt.subplots(figsize=(10, 4))
    for horizon, series in sorted(ic_by_horizon.items()):
        rolled = series.rolling(20, min_periods=1).mean()
        ax.plot(rolled.index, rolled.values, label=f"{horizon}d IC (20d roll mean)")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.legend()
    ax.set_title("Information Coefficient by Horizon")
    fig.tight_layout()
    return fig


def decile_spread_bar(decile_spreads: dict[int, pd.DataFrame]) -> matplotlib.figure.Figure:
    fig, ax = plt.subplots(figsize=(8, 4))
    horizons = sorted(decile_spreads.keys())
    means = [decile_spreads[h]["spread"].mean() for h in horizons]
    ax.bar([str(h) for h in horizons], means)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Mean Decile Spread Return by Horizon")
    ax.set_xlabel("Horizon (days)")
    ax.set_ylabel("Top-Bottom Decile Spread")
    fig.tight_layout()
    return fig
