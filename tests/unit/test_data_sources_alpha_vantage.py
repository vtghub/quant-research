from __future__ import annotations

from datetime import date

import pytest

from quant_research.core.exceptions import DataSourceError
from quant_research.core.registries import DATA_SOURCE_REGISTRY
from quant_research.data.sources.alpha_vantage_source import AlphaVantageSource


def test_alpha_vantage_is_registered() -> None:
    assert "alpha_vantage" in DATA_SOURCE_REGISTRY
    assert DATA_SOURCE_REGISTRY.get("alpha_vantage") is AlphaVantageSource


def test_missing_api_key_raises() -> None:
    source = AlphaVantageSource(api_key=None)
    with pytest.raises(DataSourceError, match="ALPHAVANTAGE_API_KEY"):
        source.fetch(["AAPL"], date(2020, 1, 1), date(2020, 2, 1))


class _FakeResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self) -> dict:
        return self._payload


def _daily_payload() -> dict:
    return {
        "Time Series (Daily)": {
            "2020-01-03": {"1. open": "10.0", "2. high": "11.0", "3. low": "9.5", "4. close": "10.5", "5. volume": "1000"},
            "2020-01-06": {"1. open": "10.5", "2. high": "11.5", "3. low": "10.0", "4. close": "11.0", "5. volume": "1200"},
        }
    }


def test_fetch_normalizes_schema_and_filters_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "quant_research.data.sources.alpha_vantage_source.requests.get",
        lambda *a, **k: _FakeResponse(_daily_payload()),
    )
    source = AlphaVantageSource(api_key="dummy")
    df = source.fetch(["AAPL"], date(2020, 1, 1), date(2020, 1, 10))

    assert list(df.columns) == ["date", "symbol", "open", "high", "low", "close", "adj_close", "volume", "source"]
    assert len(df) == 2
    assert (df["close"] == df["adj_close"]).all()  # free tier has no adjusted series
    assert (df["source"] == "alpha_vantage").all()


def test_fetch_raises_on_rate_limit_note(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "quant_research.data.sources.alpha_vantage_source.requests.get",
        lambda *a, **k: _FakeResponse({"Note": "Thank you for using Alpha Vantage! Our standard API rate limit..."}),
    )
    source = AlphaVantageSource(api_key="dummy")
    with pytest.raises(DataSourceError, match="rate-limited"):
        source.fetch(["AAPL"], date(2020, 1, 1), date(2020, 1, 10))


def test_fetch_raises_on_empty_series(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "quant_research.data.sources.alpha_vantage_source.requests.get",
        lambda *a, **k: _FakeResponse({"Error Message": "Invalid API call"}),
    )
    source = AlphaVantageSource(api_key="dummy")
    with pytest.raises(DataSourceError, match="no data"):
        source.fetch(["ZZZ"], date(2020, 1, 1), date(2020, 1, 10))
