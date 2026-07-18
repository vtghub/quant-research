from __future__ import annotations

from datetime import date

import pytest

from quant_research.core.exceptions import DataSourceError
from quant_research.core.registries import FUNDAMENTALS_SOURCE_REGISTRY
from quant_research.data.sources.sec_edgar_source import SecEdgarSource


def test_sec_edgar_is_registered() -> None:
    assert "sec_edgar" in FUNDAMENTALS_SOURCE_REGISTRY
    assert FUNDAMENTALS_SOURCE_REGISTRY.get("sec_edgar") is SecEdgarSource


def test_missing_user_agent_raises() -> None:
    source = SecEdgarSource(user_agent=None)
    with pytest.raises(DataSourceError, match="User-Agent"):
        source.fetch(["AAPL"], ["Assets"], date(2020, 1, 1), date(2021, 1, 1))


TICKER_MAP_PAYLOAD = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp"},
}


def _concept_payload(values: list[tuple[str, float]]) -> dict:
    return {
        "units": {
            "USD": [{"end": end, "val": val, "form": "10-K"} for end, val in values],
        }
    }


class _FakeResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self) -> dict:
        return self._payload


def test_fetch_maps_ticker_to_cik_and_normalizes_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url, headers=None, timeout=None, **kwargs):
        if "company_tickers" in url:
            return _FakeResponse(TICKER_MAP_PAYLOAD)
        return _FakeResponse(_concept_payload([("2020-03-31", 100.0), ("2020-06-30", 110.0)]))

    monkeypatch.setattr("quant_research.data.sources.sec_edgar_source.requests.get", fake_get)

    source = SecEdgarSource(user_agent="Test Agent test@example.com")
    df = source.fetch(["AAPL"], ["Assets"], date(2020, 1, 1), date(2020, 12, 31))

    assert list(df.columns) == ["date", "symbol", "concept", "value", "source"]
    assert (df["symbol"] == "AAPL").all()
    assert (df["concept"] == "Assets").all()
    assert (df["source"] == "sec_edgar").all()
    assert len(df) == 2


def test_unknown_ticker_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "quant_research.data.sources.sec_edgar_source.requests.get",
        lambda url, headers=None, timeout=None, **kwargs: _FakeResponse(TICKER_MAP_PAYLOAD),
    )
    source = SecEdgarSource(user_agent="Test Agent test@example.com")
    with pytest.raises(DataSourceError, match="no CIK found"):
        source.fetch(["NOTAREALTICKER"], ["Assets"], date(2020, 1, 1), date(2020, 12, 31))


def test_fetch_filters_to_date_range(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url, headers=None, timeout=None, **kwargs):
        if "company_tickers" in url:
            return _FakeResponse(TICKER_MAP_PAYLOAD)
        return _FakeResponse(
            _concept_payload([("2019-12-31", 90.0), ("2020-03-31", 100.0), ("2021-06-30", 200.0)])
        )

    monkeypatch.setattr("quant_research.data.sources.sec_edgar_source.requests.get", fake_get)

    source = SecEdgarSource(user_agent="Test Agent test@example.com")
    df = source.fetch(["AAPL"], ["Assets"], date(2020, 1, 1), date(2020, 12, 31))

    assert len(df) == 1
    assert df["value"].iloc[0] == 100.0
