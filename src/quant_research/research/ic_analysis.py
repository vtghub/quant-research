from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd

from quant_research.research.forward_returns import forward_returns


def information_coefficient(signal: pd.DataFrame, fwd_ret: pd.DataFrame, method: str = "spearman") -> pd.Series:
    """Per-date cross-sectional correlation between a signal and the forward
    return it's meant to predict."""
    s, r = signal.align(fwd_ret, join="inner")
    return s.corrwith(r, axis=1, method=method)


def decile_spread_returns(signal: pd.DataFrame, fwd_ret: pd.DataFrame, n_quantiles: int = 5) -> pd.DataFrame:
    """Per date: bucket symbols into n_quantiles by signal value, equal-weight
    mean forward return per bucket (q1 = lowest signal .. qN = highest), plus a
    'spread' column = qN - q1."""
    s, r = signal.align(fwd_ret, join="inner")
    labels = [f"q{i + 1}" for i in range(n_quantiles)]
    rows: list[dict[str, float]] = []

    for idx in s.index:
        row_signal = s.loc[idx]
        row_ret = r.loc[idx]
        valid = row_signal.notna() & row_ret.notna()
        record: dict[str, float] = {"date": idx}

        if valid.sum() < n_quantiles:
            rows.append({**record, **{label: np.nan for label in labels}, "spread": np.nan})
            continue

        try:
            buckets = pd.qcut(row_signal[valid], n_quantiles, labels=False, duplicates="drop")
        except ValueError:
            rows.append({**record, **{label: np.nan for label in labels}, "spread": np.nan})
            continue

        bucket_means = row_ret[valid].groupby(buckets).mean()
        for i, label in enumerate(labels):
            record[label] = float(bucket_means.get(i, np.nan))
        record["spread"] = record[labels[-1]] - record[labels[0]]
        rows.append(record)

    return pd.DataFrame(rows).set_index("date")


def signal_autocorrelation(signal: pd.DataFrame, lag: int = 1, method: str = "spearman") -> pd.Series:
    """Per-date cross-sectional correlation between the signal and its own lag --
    a decay/turnover proxy (values near 1.0 mean the signal barely changes
    day-to-day; values near 0 mean it's noisy/high-turnover)."""
    shifted = signal.shift(lag)
    return signal.corrwith(shifted, axis=1, method=method)


@dataclass
class ICSummary:
    horizon: int
    mean_ic: float
    std_ic: float
    ic_ir: float
    t_stat: float
    hit_rate: float


def summarize_ic(ic_series: pd.Series, horizon: int) -> ICSummary:
    clean = ic_series.dropna()
    n = len(clean)
    mean_ic = float(clean.mean()) if n else 0.0
    std_ic = float(clean.std(ddof=1)) if n > 1 else 0.0
    ic_ir = mean_ic / std_ic if std_ic else 0.0
    t_stat = mean_ic / (std_ic / np.sqrt(n)) if std_ic and n else 0.0
    if n == 0:
        hit_rate = 0.0
    elif mean_ic >= 0:
        hit_rate = float((clean > 0).mean())
    else:
        hit_rate = float((clean < 0).mean())
    return ICSummary(horizon=horizon, mean_ic=mean_ic, std_ic=std_ic, ic_ir=ic_ir, t_stat=t_stat, hit_rate=hit_rate)


@dataclass
class ICAnalysisResult:
    summaries: dict[int, ICSummary]
    ic_series: dict[int, pd.Series]
    decile_spreads: dict[int, pd.DataFrame]
    autocorrelation: pd.Series


def run_ic_analysis(
    prices: pd.DataFrame,
    signal_df: pd.DataFrame,
    horizons: Sequence[int],
    n_quantiles: int = 5,
) -> ICAnalysisResult:
    fwd = forward_returns(prices, horizons)
    ic_series: dict[int, pd.Series] = {}
    summaries: dict[int, ICSummary] = {}
    spreads: dict[int, pd.DataFrame] = {}

    for h in horizons:
        ic = information_coefficient(signal_df, fwd[h])
        ic_series[h] = ic
        summaries[h] = summarize_ic(ic, h)
        spreads[h] = decile_spread_returns(signal_df, fwd[h], n_quantiles)

    return ICAnalysisResult(
        summaries=summaries,
        ic_series=ic_series,
        decile_spreads=spreads,
        autocorrelation=signal_autocorrelation(signal_df),
    )
