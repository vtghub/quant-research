from __future__ import annotations

import os
from datetime import date
from typing import Sequence

import pandas as pd

from quant_research.core.exceptions import DataSourceError
from quant_research.core.registries import MACRO_SOURCE_REGISTRY
from quant_research.data.base import MacroDataSource, normalize_macro


@MACRO_SOURCE_REGISTRY.register("fred")
class FredSource(MacroDataSource):
    """Macro series (FEDFUNDS, CPIAUCSL, yield-curve components, ...) via the free
    FRED API. Requires a free API key (https://fred.stlouisfed.org/docs/api/api_key.html)
    passed explicitly or via the FRED_API_KEY env var. `fredapi` is an optional
    extra (`pip install quant-research[fred]`) -- its absence never breaks the
    base install, only this source's use."""

    name = "fred"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("FRED_API_KEY")

    def fetch(self, series_ids: Sequence[str], start: date, end: date) -> pd.DataFrame:
        try:
            from fredapi import Fred
        except ImportError as exc:
            raise DataSourceError(
                "fredapi is not installed; run `pip install 'quant-research[fred]'`"
            ) from exc

        if not self.api_key:
            raise DataSourceError(
                "FRED_API_KEY not set. Get a free key at "
                "https://fred.stlouisfed.org/docs/api/api_key.html and set FRED_API_KEY."
            )

        fred = Fred(api_key=self.api_key)
        frames = []
        for series_id in series_ids:
            try:
                series = fred.get_series(series_id, observation_start=start, observation_end=end)
            except Exception as exc:
                raise DataSourceError(f"fred fetch failed for {series_id}: {exc}") from exc
            if series is None or series.empty:
                raise DataSourceError(f"fred returned no data for {series_id} [{start}..{end}]")
            frames.append(pd.DataFrame({"date": series.index, "series_id": series_id, "value": series.values}))

        combined = pd.concat(frames, ignore_index=True)
        return normalize_macro(combined, self.name)
