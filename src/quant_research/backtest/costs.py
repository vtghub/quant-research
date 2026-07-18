from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class CostModel(ABC):
    @abstractmethod
    def cost(self, weight_diff: pd.DataFrame, prices: pd.DataFrame | None = None) -> pd.Series:
        """Return a per-date cost series (as a fraction of capital) given the
        day-over-day change in portfolio weights."""


class BpsCostModel(CostModel):
    """Flat basis-points-per-trade cost, proportional to turnover (sum of |weight
    changes| across the book each day)."""

    def __init__(self, bps_per_trade: float = 5.0) -> None:
        self.bps_per_trade = bps_per_trade

    def cost(self, weight_diff: pd.DataFrame, prices: pd.DataFrame | None = None) -> pd.Series:
        turnover = weight_diff.abs().sum(axis=1)
        return turnover * (self.bps_per_trade / 10_000.0)
