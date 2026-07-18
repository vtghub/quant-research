from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from quant_research.cache.parquet_backend import ParquetCacheBackend
from quant_research.core.hooks import HookEvent, HookManager
from quant_research.data.access import DataAccessLayer


class CountingWrapper:
    """Wraps a data source and counts fetch() calls, to prove the cache prevents refetching."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.name = inner.name
        self.calls: list[tuple] = []

    def fetch(self, symbols, start, end, interval="1d"):
        self.calls.append((tuple(symbols), start, end, interval))
        return self.inner.fetch(symbols, start, end, interval)


@pytest.fixture
def access(tmp_path) -> DataAccessLayer:
    cache = ParquetCacheBackend(root_dir=tmp_path)
    return DataAccessLayer(cache, HookManager())


def test_first_fetch_hits_source_and_populates_cache(access: DataAccessLayer, fake_data_source) -> None:
    source = CountingWrapper(fake_data_source)
    df = access.get_ohlcv_long(source, ["AAA"], date(2020, 1, 2), date(2020, 1, 10))

    assert len(source.calls) == 1
    assert not df.empty
    assert set(df["symbol"]) == {"AAA"}


def test_second_fetch_within_cached_range_hits_cache_not_source(
    access: DataAccessLayer, fake_data_source
) -> None:
    source = CountingWrapper(fake_data_source)
    access.get_ohlcv_long(source, ["AAA"], date(2020, 1, 2), date(2020, 3, 1))
    assert len(source.calls) == 1

    df2 = access.get_ohlcv_long(source, ["AAA"], date(2020, 1, 10), date(2020, 2, 1))
    assert len(source.calls) == 1  # no new fetch -- fully covered by cache
    assert df2["date"].min() >= pd.Timestamp("2020-01-10")
    assert df2["date"].max() <= pd.Timestamp("2020-02-01")


def test_fetch_outside_cached_range_triggers_refetch(access: DataAccessLayer, fake_data_source) -> None:
    source = CountingWrapper(fake_data_source)
    access.get_ohlcv_long(source, ["AAA"], date(2020, 6, 1), date(2020, 6, 10))
    assert len(source.calls) == 1

    access.get_ohlcv_long(source, ["AAA"], date(2020, 1, 2), date(2020, 6, 10))
    assert len(source.calls) == 2  # requested range extends before cached range


def test_hooks_fire_before_and_after_fetch(access: DataAccessLayer, fake_data_source) -> None:
    events: list[str] = []
    access.hooks.register(HookEvent.BEFORE_FETCH, lambda ctx: events.append("before"))
    access.hooks.register(HookEvent.AFTER_FETCH, lambda ctx: events.append("after"))

    access.get_ohlcv_long(fake_data_source, ["AAA"], date(2020, 1, 2), date(2020, 1, 10))

    assert events == ["before", "after"]


def test_to_wide_pivots_on_price_field(access: DataAccessLayer, fake_data_source) -> None:
    long_df = access.get_ohlcv_long(fake_data_source, ["AAA", "BBB"], date(2020, 1, 2), date(2020, 2, 1))
    wide = DataAccessLayer.to_wide(long_df, price_field="adj_close")

    assert set(wide.columns) == {"AAA", "BBB"}
    assert wide.index.is_monotonic_increasing


def test_broadcast_macro_forward_fills_onto_calendar_and_broadcasts_columns() -> None:
    macro_long = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-01", "2020-02-01", "2020-03-01"]),
            "series_id": ["FEDFUNDS"] * 3,
            "value": [1.0, 2.0, 3.0],
        }
    )
    calendar = pd.bdate_range("2020-01-01", "2020-03-10")

    wide = DataAccessLayer.broadcast_macro(macro_long, "FEDFUNDS", calendar, ["AAA", "BBB"])

    assert set(wide.columns) == {"AAA", "BBB"}
    assert (wide["AAA"] == wide["BBB"]).all()
    # forward-filled: value on 2020-02-15 should still be the 2020-02-01 print (2.0)
    assert wide.loc[pd.Timestamp("2020-02-17"), "AAA"] == 2.0
