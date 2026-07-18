from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

import pandas as pd


class Strategy(ABC):
    """Turns a signal panel into target portfolio weights.

    generate_weights must decide each row's weights using only information
    available as of that row's date -- it must NOT pre-shift for lookahead
    avoidance. BacktestEngine owns the single t -> t+1 shift (see backtest/engine.py).
    """

    name: ClassVar[str]

    def __init__(self, **params: Any) -> None:
        self.params = params

    @abstractmethod
    def generate_weights(self, signal_df: pd.DataFrame, prices: pd.DataFrame | None = None) -> pd.DataFrame:
        """Returns a wide date x symbol frame of target weights, same shape as signal_df."""
