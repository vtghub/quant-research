from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class MembershipRecord:
    symbol: str
    start_date: pd.Timestamp
    end_date: pd.Timestamp | None  # None = still a member (open-ended)


class UniverseProvider(ABC):
    """Resolves which symbols were valid universe members as of any given date.

    Every OHLCVDataSource fetch and every Signal is computed across
    `all_symbols_ever()` (so a delisted/removed symbol's price history is
    still available up to its removal), while `membership_mask` is applied
    afterward to exclude a symbol from ranking/trading on dates it wasn't
    actually a member -- this is what makes a broader-than-fixed universe
    (e.g. "S&P 500 over time") survivorship-bias-free rather than silently
    using only currently-listed constituents for the whole backtest.
    """

    @abstractmethod
    def all_symbols_ever(self) -> list[str]:
        """Every symbol that was ever a member, for data-fetch purposes."""

    @abstractmethod
    def membership_mask(self, calendar_index: pd.DatetimeIndex) -> pd.DataFrame:
        """Boolean date x symbol frame (columns = all_symbols_ever()); True
        where that symbol was a valid member as of that date."""
