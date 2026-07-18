from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from quant_research.core.exceptions import ConfigError
from quant_research.core.registries import UNIVERSE_PROVIDER_REGISTRY
from quant_research.universe.base import MembershipRecord, UniverseProvider


def load_membership_csv(path: str | Path) -> list[MembershipRecord]:
    """Reads a membership-changes CSV with columns symbol,start_date,end_date
    (end_date blank/omitted = still an active member). There is no bundled
    free, reliably-maintained historical index-membership dataset to fetch
    this from automatically -- see README for how to source one (e.g.
    Wikipedia's "List of S&P 500 companies" changes table, or a
    community-maintained CSV) and format it into this shape."""
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"point-in-time membership CSV not found: {path}")

    df = pd.read_csv(path)
    required = {"symbol", "start_date"}
    missing = required - set(df.columns)
    if missing:
        raise ConfigError(f"membership CSV {path} is missing required column(s): {sorted(missing)}")
    if "end_date" not in df.columns:
        df["end_date"] = pd.NA

    records = []
    for row in df.itertuples(index=False):
        end_raw = getattr(row, "end_date")
        end_date = None if pd.isna(end_raw) else pd.Timestamp(end_raw)
        records.append(
            MembershipRecord(symbol=str(row.symbol), start_date=pd.Timestamp(row.start_date), end_date=end_date)
        )
    if not records:
        raise ConfigError(f"membership CSV {path} contained no rows")
    return records


@UNIVERSE_PROVIDER_REGISTRY.register("point_in_time")
class PointInTimeUniverse(UniverseProvider):
    """A symbol is a member on date d if any of its MembershipRecords covers d
    (start_date <= d <= end_date, or start_date <= d with end_date=None). A
    symbol can have multiple non-contiguous records (removed, later re-added)."""

    def __init__(
        self,
        membership_csv: str | Path | None = None,
        records: Sequence[MembershipRecord] | None = None,
        **_: Any,
    ) -> None:
        if records is not None:
            self.records = list(records)
        elif membership_csv is not None:
            self.records = load_membership_csv(membership_csv)
        else:
            raise ConfigError("PointInTimeUniverse requires either membership_csv= or records=")

    def all_symbols_ever(self) -> list[str]:
        return sorted({r.symbol for r in self.records})

    def membership_mask(self, calendar_index: pd.DatetimeIndex) -> pd.DataFrame:
        symbols = self.all_symbols_ever()
        mask = pd.DataFrame(False, index=calendar_index, columns=symbols)
        for record in self.records:
            end = record.end_date if record.end_date is not None else calendar_index.max()
            covered = (calendar_index >= record.start_date) & (calendar_index <= end)
            mask.loc[covered, record.symbol] = True
        return mask
