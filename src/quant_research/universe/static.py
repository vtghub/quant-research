from __future__ import annotations

from typing import Any, Sequence

import pandas as pd

from quant_research.core.registries import UNIVERSE_PROVIDER_REGISTRY
from quant_research.universe.base import UniverseProvider


@UNIVERSE_PROVIDER_REGISTRY.register("static")
class StaticUniverse(UniverseProvider):
    """The default/current behavior: a fixed symbol list for the entire
    backtest period -- every symbol is a member on every date."""

    def __init__(self, symbols: Sequence[str], **_: Any) -> None:
        self.symbols = list(symbols)

    def all_symbols_ever(self) -> list[str]:
        return self.symbols

    def membership_mask(self, calendar_index: pd.DatetimeIndex) -> pd.DataFrame:
        return pd.DataFrame(True, index=calendar_index, columns=self.symbols)
