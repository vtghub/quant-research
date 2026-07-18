from __future__ import annotations

import os
from datetime import date
from typing import Sequence

import pandas as pd
import requests

from quant_research.core.exceptions import DataSourceError
from quant_research.core.registries import MACRO_SOURCE_REGISTRY
from quant_research.data.base import MacroDataSource, normalize_macro

BASE_URL = "https://data.nasdaq.com/api/v3/datasets/{dataset_code}/data.json"


@MACRO_SOURCE_REGISTRY.register("nasdaq_data_link")
class NasdaqDataLinkSource(MacroDataSource):
    """Free datasets from Nasdaq Data Link (formerly Quandl), e.g. 'LBMA/GOLD'.
    Requires a free API key (https://data.nasdaq.com/sign-up) via api_key= or
    NASDAQ_DATA_LINK_API_KEY. Treats each `series_id` as a dataset code; Nasdaq
    Data Link datasets have heterogeneous, dataset-specific columns (not a fixed
    OHLC shape), so this picks one numeric value column per dataset -- by
    default the first non-date column, or override per series via
    value_columns={"LBMA/GOLD": "USD (PM)"} -- and folds it into the same
    (date, series_id, value) macro schema as FRED, so it plugs into
    macro_overlay / broadcast_macro identically."""

    name = "nasdaq_data_link"

    def __init__(self, api_key: str | None = None, value_columns: dict[str, str] | None = None) -> None:
        self.api_key = api_key or os.environ.get("NASDAQ_DATA_LINK_API_KEY")
        self.value_columns = value_columns or {}

    def fetch(self, series_ids: Sequence[str], start: date, end: date) -> pd.DataFrame:
        frames = [self._fetch_one(dataset_code, start, end) for dataset_code in series_ids]
        combined = pd.concat(frames, ignore_index=True)
        return normalize_macro(combined, self.name)

    def _fetch_one(self, dataset_code: str, start: date, end: date) -> pd.DataFrame:
        if not self.api_key:
            raise DataSourceError(
                "NASDAQ_DATA_LINK_API_KEY not set. Get a free key at "
                "https://data.nasdaq.com/sign-up and set it, or pass api_key=."
            )

        params = {
            "api_key": self.api_key,
            "start_date": pd.Timestamp(start).strftime("%Y-%m-%d"),
            "end_date": pd.Timestamp(end).strftime("%Y-%m-%d"),
        }
        try:
            response = requests.get(BASE_URL.format(dataset_code=dataset_code), params=params, timeout=30)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise DataSourceError(f"nasdaq_data_link fetch failed for {dataset_code}: {exc}") from exc

        dataset = payload.get("dataset_data") or payload.get("dataset")
        if not dataset or not dataset.get("data"):
            raise DataSourceError(f"nasdaq_data_link returned no data for {dataset_code} [{start}..{end}]")

        column_names = dataset["column_names"]
        value_column = self.value_columns.get(dataset_code, column_names[1])  # column 0 is always Date
        value_idx = column_names.index(value_column)

        rows = [
            {"date": record[0], "series_id": dataset_code, "value": record[value_idx]}
            for record in dataset["data"]
            if record[value_idx] is not None
        ]
        if not rows:
            raise DataSourceError(f"nasdaq_data_link: '{value_column}' had no non-null values for {dataset_code}")
        return pd.DataFrame(rows)
