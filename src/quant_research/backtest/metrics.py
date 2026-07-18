from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


def annualized_vol(daily_returns: pd.Series, periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    if daily_returns.std(ddof=0) == 0 or daily_returns.empty:
        return 0.0
    return float(daily_returns.std(ddof=0) * np.sqrt(periods_per_year))


def cagr(equity_curve: pd.Series, periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    if len(equity_curve) < 2 or equity_curve.iloc[0] <= 0:
        return 0.0
    total_return = equity_curve.iloc[-1] / equity_curve.iloc[0]
    years = len(equity_curve) / periods_per_year
    if years <= 0 or total_return <= 0:
        return 0.0
    return float(total_return ** (1.0 / years) - 1.0)


def sharpe_ratio(
    daily_returns: pd.Series, risk_free: float = 0.0, periods_per_year: int = TRADING_DAYS_PER_YEAR
) -> float:
    excess = daily_returns - risk_free / periods_per_year
    std = excess.std(ddof=0)
    if std == 0 or excess.empty:
        return 0.0
    return float(excess.mean() / std * np.sqrt(periods_per_year))


def sortino_ratio(
    daily_returns: pd.Series, risk_free: float = 0.0, periods_per_year: int = TRADING_DAYS_PER_YEAR
) -> float:
    excess = daily_returns - risk_free / periods_per_year
    downside = excess.where(excess < 0, 0.0)
    downside_std = downside.std(ddof=0)
    if downside_std == 0 or excess.empty:
        return 0.0
    return float(excess.mean() / downside_std * np.sqrt(periods_per_year))


def max_drawdown(equity_curve: pd.Series) -> float:
    if equity_curve.empty:
        return 0.0
    running_max = equity_curve.cummax()
    drawdown = equity_curve / running_max - 1.0
    return float(drawdown.min())


def calmar_ratio(equity_curve: pd.Series, periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    mdd = max_drawdown(equity_curve)
    if mdd == 0:
        return 0.0
    return float(cagr(equity_curve, periods_per_year) / abs(mdd))


def compute_metrics(daily_returns: pd.Series, equity_curve: pd.Series) -> dict[str, float]:
    return {
        "cagr": cagr(equity_curve),
        "annualized_vol": annualized_vol(daily_returns),
        "sharpe": sharpe_ratio(daily_returns),
        "sortino": sortino_ratio(daily_returns),
        "max_drawdown": max_drawdown(equity_curve),
        "calmar": calmar_ratio(equity_curve),
        "total_return": float(equity_curve.iloc[-1] / equity_curve.iloc[0] - 1.0) if len(equity_curve) else 0.0,
    }
