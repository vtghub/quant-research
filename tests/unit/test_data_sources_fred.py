from __future__ import annotations

import sys
import types
from datetime import date

import pandas as pd
import pytest

from quant_research.core.exceptions import DataSourceError
from quant_research.core.registries import MACRO_SOURCE_REGISTRY
from quant_research.data.sources.fred_source import FredSource


def test_fred_is_registered() -> None:
    assert "fred" in MACRO_SOURCE_REGISTRY
    assert MACRO_SOURCE_REGISTRY.get("fred") is FredSource


class _FakeFredClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def get_series(self, series_id, observation_start, observation_end):
        dates = pd.bdate_range("2023-01-02", periods=5)
        return pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], index=dates)


class _EmptyFredClient:
    def __init__(self, api_key: str) -> None:
        pass

    def get_series(self, series_id, observation_start, observation_end):
        return pd.Series(dtype=float)


def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    source = FredSource()
    with pytest.raises(DataSourceError, match="FRED_API_KEY"):
        source.fetch(["FEDFUNDS"], date(2023, 1, 1), date(2023, 1, 10))


def test_missing_fredapi_dependency_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "fredapi", None)
    source = FredSource(api_key="dummy")
    with pytest.raises(DataSourceError, match="fredapi is not installed"):
        source.fetch(["FEDFUNDS"], date(2023, 1, 1), date(2023, 1, 10))


def test_fetch_normalizes_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = types.SimpleNamespace(Fred=_FakeFredClient)
    monkeypatch.setitem(sys.modules, "fredapi", fake_module)

    source = FredSource(api_key="dummy")
    df = source.fetch(["FEDFUNDS", "CPIAUCSL"], date(2023, 1, 1), date(2023, 1, 10))

    assert list(df.columns) == ["date", "series_id", "value", "source"]
    assert set(df["series_id"]) == {"FEDFUNDS", "CPIAUCSL"}
    assert (df["source"] == "fred").all()


def test_fetch_raises_on_empty_series(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = types.SimpleNamespace(Fred=_EmptyFredClient)
    monkeypatch.setitem(sys.modules, "fredapi", fake_module)

    source = FredSource(api_key="dummy")
    with pytest.raises(DataSourceError, match="no data"):
        source.fetch(["FEDFUNDS"], date(2023, 1, 1), date(2023, 1, 10))
