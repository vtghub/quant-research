from __future__ import annotations

import pandas as pd
import pytest

from quant_research.core.exceptions import HookAbort
from quant_research.core.hooks import HookEvent, HookManager
from quant_research.hooks.builtin import data_quality_hooks, logging_hooks


def test_logging_hooks_register_without_raising() -> None:
    hooks = HookManager()
    logging_hooks.register(hooks)
    assert hooks.handler_count(HookEvent.BEFORE_FETCH) == 1
    assert hooks.handler_count(HookEvent.AFTER_FETCH) == 1


def test_logging_hooks_fire_without_error(caplog: pytest.LogCaptureFixture) -> None:
    hooks = HookManager()
    logging_hooks.register(hooks)
    with caplog.at_level("INFO"):
        hooks.fire(HookEvent.BEFORE_FETCH, symbol="AAA", source="yfinance", start="2020-01-01", end="2020-02-01")
        hooks.fire(HookEvent.AFTER_FETCH, symbol="AAA", source="yfinance", df=pd.DataFrame({"close": [1.0]}))
    assert "fetching AAA" in caplog.text
    assert "fetched 1 rows" in caplog.text


def test_data_quality_hook_aborts_on_high_null_fraction() -> None:
    hooks = HookManager()
    data_quality_hooks.register(hooks, max_null_frac=0.05)

    bad_df = pd.DataFrame(
        {"date": pd.bdate_range("2020-01-01", periods=10), "close": [None] * 8 + [1.0, 2.0]}
    )
    with pytest.raises(HookAbort, match="exceeds"):
        hooks.fire(HookEvent.AFTER_FETCH, symbol="AAA", source="yfinance", df=bad_df)


def test_data_quality_hook_passes_on_clean_data() -> None:
    hooks = HookManager()
    data_quality_hooks.register(hooks, max_null_frac=0.05)

    good_df = pd.DataFrame(
        {"date": pd.bdate_range("2020-01-01", periods=10), "close": list(range(10))}
    )
    hooks.fire(HookEvent.AFTER_FETCH, symbol="AAA", source="yfinance", df=good_df)  # should not raise


def test_data_quality_hook_warns_on_large_gap(caplog: pytest.LogCaptureFixture) -> None:
    hooks = HookManager()
    data_quality_hooks.register(hooks, max_null_frac=0.5, max_gap_days=7)

    dates = list(pd.bdate_range("2020-01-01", periods=5)) + list(pd.bdate_range("2020-03-01", periods=5))
    gappy_df = pd.DataFrame({"date": dates, "close": list(range(10))})

    with caplog.at_level("WARNING"):
        hooks.fire(HookEvent.AFTER_FETCH, symbol="AAA", source="yfinance", df=gappy_df)
    assert "gap" in caplog.text


def test_data_quality_hook_handles_empty_df_gracefully() -> None:
    hooks = HookManager()
    data_quality_hooks.register(hooks)
    hooks.fire(HookEvent.AFTER_FETCH, symbol="AAA", source="yfinance", df=pd.DataFrame())  # should not raise
