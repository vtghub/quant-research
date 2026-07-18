from __future__ import annotations

from datetime import date

import pytest

from quant_research.core.exceptions import DataSourceError
from quant_research.core.registries import MACRO_SOURCE_REGISTRY
from quant_research.data.sources.nasdaq_data_link_source import NasdaqDataLinkSource


def test_nasdaq_data_link_is_registered() -> None:
    assert "nasdaq_data_link" in MACRO_SOURCE_REGISTRY
    assert MACRO_SOURCE_REGISTRY.get("nasdaq_data_link") is NasdaqDataLinkSource


def test_missing_api_key_raises() -> None:
    source = NasdaqDataLinkSource(api_key=None)
    with pytest.raises(DataSourceError, match="NASDAQ_DATA_LINK_API_KEY"):
        source.fetch(["LBMA/GOLD"], date(2020, 1, 1), date(2020, 2, 1))


class _FakeResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self) -> dict:
        return self._payload


def _gold_payload() -> dict:
    return {
        "dataset_data": {
            "column_names": ["Date", "USD (AM)", "USD (PM)", "GBP (AM)", "GBP (PM)"],
            "data": [
                ["2020-01-06", 1500.0, 1505.0, 1150.0, 1152.0],
                ["2020-01-03", 1490.0, 1495.0, 1140.0, 1142.0],
            ],
        }
    }


def test_fetch_defaults_to_first_value_column(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "quant_research.data.sources.nasdaq_data_link_source.requests.get",
        lambda *a, **k: _FakeResponse(_gold_payload()),
    )
    source = NasdaqDataLinkSource(api_key="dummy")
    df = source.fetch(["LBMA/GOLD"], date(2020, 1, 1), date(2020, 1, 10))

    assert list(df.columns) == ["date", "series_id", "value", "source"]
    assert (df["series_id"] == "LBMA/GOLD").all()
    assert set(df["value"]) == {1500.0, 1490.0}  # "USD (AM)" is the default (first value column)


def test_fetch_respects_value_column_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "quant_research.data.sources.nasdaq_data_link_source.requests.get",
        lambda *a, **k: _FakeResponse(_gold_payload()),
    )
    source = NasdaqDataLinkSource(api_key="dummy", value_columns={"LBMA/GOLD": "USD (PM)"})
    df = source.fetch(["LBMA/GOLD"], date(2020, 1, 1), date(2020, 1, 10))

    assert set(df["value"]) == {1505.0, 1495.0}


def test_fetch_raises_on_empty_dataset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "quant_research.data.sources.nasdaq_data_link_source.requests.get",
        lambda *a, **k: _FakeResponse({"dataset_data": {"column_names": ["Date", "Value"], "data": []}}),
    )
    source = NasdaqDataLinkSource(api_key="dummy")
    with pytest.raises(DataSourceError, match="no data"):
        source.fetch(["EMPTY/SET"], date(2020, 1, 1), date(2020, 1, 10))
