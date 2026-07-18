from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from quant_research.core.exceptions import DataSourceError
from quant_research.core.registries import DATA_SOURCE_REGISTRY
from quant_research.data.sources.coingecko_source import CoinGeckoSource, _to_coingecko_id


def test_to_coingecko_id_strips_quote_suffix() -> None:
    assert _to_coingecko_id("BTC-USD") == "bitcoin"
    assert _to_coingecko_id("ETHUSDT") == "ethereum"
    assert _to_coingecko_id("btc") == "bitcoin"


def test_to_coingecko_id_unknown_symbol_raises() -> None:
    with pytest.raises(DataSourceError, match="no CoinGecko id mapping"):
        _to_coingecko_id("NOTACOIN-USD")


def test_coingecko_is_registered() -> None:
    assert "coingecko" in DATA_SOURCE_REGISTRY
    assert DATA_SOURCE_REGISTRY.get("coingecko") is CoinGeckoSource


class _FakeResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self) -> dict:
        return self._payload


def _sample_payload() -> dict:
    base_ms = int(pd.Timestamp("2023-01-03").timestamp() * 1000)
    hour_ms = 3_600_000
    prices = [[base_ms + i * hour_ms, 100.0 + i] for i in range(30)]
    volumes = [[base_ms + i * hour_ms, 1_000.0] for i in range(30)]
    return {"prices": prices, "total_volumes": volumes}


def test_fetch_resamples_price_series_to_daily_ohlc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "quant_research.data.sources.coingecko_source.requests.get",
        lambda *a, **k: _FakeResponse(_sample_payload()),
    )
    source = CoinGeckoSource()
    df = source.fetch(["BTC-USD"], date(2023, 1, 1), date(2023, 1, 10))

    assert list(df.columns) == ["date", "symbol", "open", "high", "low", "close", "adj_close", "volume", "source"]
    assert (df["source"] == "coingecko").all()
    assert (df["high"] >= df["low"]).all()
    assert (df["close"] == df["adj_close"]).all()


def test_fetch_raises_on_empty_prices(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "quant_research.data.sources.coingecko_source.requests.get",
        lambda *a, **k: _FakeResponse({"prices": [], "total_volumes": []}),
    )
    source = CoinGeckoSource()
    with pytest.raises(DataSourceError, match="no data"):
        source.fetch(["BTC-USD"], date(2023, 1, 1), date(2023, 1, 10))
