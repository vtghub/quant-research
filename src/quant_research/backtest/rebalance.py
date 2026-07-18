from __future__ import annotations

import numpy as np
import pandas as pd

_FREQ_CODE = {"weekly": "W", "monthly": "M"}


def apply_rebalance_schedule(weights: pd.DataFrame, frequency: str = "daily") -> pd.DataFrame:
    """Holds weights constant between rebalance dates: 'daily' rebalances every
    day (no-op); 'weekly'/'monthly' only update weights on the first trading day
    of each period, forward-filling in between -- so day-to-day signal noise on
    off-rebalance days doesn't create phantom turnover/cost in the backtest."""
    if frequency == "daily" or weights.empty:
        return weights

    periods = weights.index.to_period(_FREQ_CODE[frequency])
    period_values = periods.values
    is_rebalance_day = np.concatenate([[True], period_values[1:] != period_values[:-1]])

    masked = weights.where(pd.Series(is_rebalance_day, index=weights.index), other=np.nan)
    return masked.ffill().fillna(0.0)
