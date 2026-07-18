from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

import pandas as pd


class Signal(ABC):
    """A signal turns a wide date x symbol price panel into a same-shaped score panel.

    NaN during warm-up windows is expected and MUST be tolerated by downstream
    strategy/backtest code (treated as zero weight), not treated as an error.
    """

    name: ClassVar[str]

    def __init__(self, **params: Any) -> None:
        self.params = params

    @abstractmethod
    def compute(self, prices: pd.DataFrame, inputs: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
        """prices: wide date-indexed frame, columns=symbols (the configured price_field).
        inputs: outputs of upstream signals this one depends_on, keyed by alias.
        Returns a wide frame with the same index/columns as prices."""
