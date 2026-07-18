from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from quant_research.core.exceptions import DataSourceError
from quant_research.core.registries import DATA_SOURCE_REGISTRY
from quant_research.data.sources.yfinance_source import YFinanceSource


def _fake_history(rows: int = 5) -> pd.DataFrame:
    dates = pd.bdate_range("2023-01-02", periods=rows)
    return pd.DataFrame(
        {
            "Open": [10.0 + i for i in range(rows)],
            "High": [11.0 + i for i in range(rows)],
            "Low": [9.0 + i for i in range(rows)],
            "Close": [10.5 + i for i in range(rows)],
            "Adj Close": [10.4 + i for i in range(rows)],
            "Volume": [1000 * (i + 1) for i in range(rows)],
        },
        index=pd.DatetimeIndex(dates, name="Date"),
    )


class _FakeTicker:
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol

    def history(self, start, end, interval, auto_adjust):
        return _fake_history()


class _EmptyTicker:
    def __init__(self, symbol: str) -> None:
        pass

    def history(self, start, end, interval, auto_adjust):
        return pd.DataFrame()


class _RaisingTicker:
    def __init__(self, symbol: str) -> None:
        pass

    def history(self, start, end, interval, auto_adjust):
        raise RuntimeError("network down")


def test_yfinance_source_is_registered() -> None:
    assert "yfinance" in DATA_SOURCE_REGISTRY
    assert DATA_SOURCE_REGISTRY.get("yfinance") is YFinanceSource


def test_fetch_normalizes_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("quant_research.data.sources.yfinance_source.yf.Ticker", _FakeTicker)
    source = YFinanceSource()

    df = source.fetch(["AAA", "BBB"], date(2023, 1, 1), date(2023, 1, 10))

    assert list(df.columns) == ["date", "symbol", "open", "high", "low", "close", "adj_close", "volume", "source"]
    assert set(df["symbol"]) == {"AAA", "BBB"}
    assert (df["source"] == "yfinance").all()
    expected_order = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(df.reset_index(drop=True), expected_order)


def test_fetch_raises_data_source_error_on_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("quant_research.data.sources.yfinance_source.yf.Ticker", _EmptyTicker)
    source = YFinanceSource()
    with pytest.raises(DataSourceError, match="no data"):
        source.fetch(["ZZZ"], date(2023, 1, 1), date(2023, 1, 10))


def test_fetch_wraps_vendor_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("quant_research.data.sources.yfinance_source.yf.Ticker", _RaisingTicker)
    source = YFinanceSource()
    with pytest.raises(DataSourceError, match="network down"):
        source.fetch(["AAA"], date(2023, 1, 1), date(2023, 1, 10))
