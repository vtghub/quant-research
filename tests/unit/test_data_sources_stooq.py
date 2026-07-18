from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from quant_research.core.exceptions import DataSourceError
from quant_research.core.registries import DATA_SOURCE_REGISTRY
from quant_research.data.sources.stooq_source import StooqSource, _to_stooq_symbol


def test_to_stooq_symbol_appends_us_suffix() -> None:
    assert _to_stooq_symbol("SPY") == "spy.us"
    assert _to_stooq_symbol("spy") == "spy.us"


def test_to_stooq_symbol_leaves_dotted_symbols_alone() -> None:
    assert _to_stooq_symbol("CDR.PL") == "cdr.pl"


def test_stooq_is_registered() -> None:
    assert "stooq" in DATA_SOURCE_REGISTRY
    assert DATA_SOURCE_REGISTRY.get("stooq") is StooqSource


class _FakeResponse:
    def __init__(self, text: str, status: int = 200) -> None:
        self.text = text
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("http error")


SAMPLE_CSV = "Date,Open,High,Low,Close,Volume\n2023-01-03,10,11,9,10.5,1000\n2023-01-04,10.5,12,10,11.5,1200\n"


def test_fetch_parses_csv_into_normalized_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "quant_research.data.sources.stooq_source.requests.get",
        lambda *a, **k: _FakeResponse(SAMPLE_CSV),
    )
    source = StooqSource()
    df = source.fetch(["SPY"], date(2023, 1, 1), date(2023, 1, 10))

    assert list(df.columns) == ["date", "symbol", "open", "high", "low", "close", "adj_close", "volume", "source"]
    assert len(df) == 2
    assert (df["source"] == "stooq").all()
    assert (df["close"] == df["adj_close"]).all()  # stooq has no separate adjusted series


def test_fetch_raises_on_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "quant_research.data.sources.stooq_source.requests.get",
        lambda *a, **k: _FakeResponse(""),
    )
    source = StooqSource()
    with pytest.raises(DataSourceError, match="no data"):
        source.fetch(["ZZZ"], date(2023, 1, 1), date(2023, 1, 10))


def test_fetch_wraps_network_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    import requests

    def _raise(*a, **k):
        raise requests.RequestException("timeout")

    monkeypatch.setattr("quant_research.data.sources.stooq_source.requests.get", _raise)
    source = StooqSource()
    with pytest.raises(DataSourceError, match="timeout"):
        source.fetch(["SPY"], date(2023, 1, 1), date(2023, 1, 10))
