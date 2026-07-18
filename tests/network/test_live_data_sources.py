"""Live-vendor tests -- excluded by default (pytest.ini: addopts = -m 'not
network'), run explicitly via `pytest -m network`. This session's own network
egress policy blocks every data vendor host outright, so these can only run
somewhere with real internet access -- e.g. .github/workflows/live-tests.yml,
which runs on GitHub's runners, not in this dev session."""
from __future__ import annotations

import os
from datetime import date, timedelta

import pytest

from quant_research.core.exceptions import DataSourceError
from quant_research.data.sources.alpha_vantage_source import AlphaVantageSource
from quant_research.data.sources.coingecko_source import CoinGeckoSource
from quant_research.data.sources.fred_source import FredSource
from quant_research.data.sources.nasdaq_data_link_source import NasdaqDataLinkSource
from quant_research.data.sources.sec_edgar_source import SecEdgarSource
from quant_research.data.sources.stooq_source import StooqSource
from quant_research.data.sources.yfinance_source import YFinanceSource

pytestmark = pytest.mark.network

RECENT_START = date.today() - timedelta(days=30)
RECENT_END = date.today() - timedelta(days=1)


def test_yfinance_live_fetch() -> None:
    df = YFinanceSource().fetch(["SPY"], RECENT_START, RECENT_END)
    assert not df.empty
    assert (df["symbol"] == "SPY").all()
    assert df["close"].notna().any()


def test_yfinance_live_crypto_fetch() -> None:
    df = YFinanceSource().fetch(["BTC-USD"], RECENT_START, RECENT_END)
    assert not df.empty
    assert df["close"].notna().any()


def test_stooq_live_fetch() -> None:
    # Stooq is known to serve non-CSV responses (bot-check pages, empty bodies)
    # to automated requests from datacenter/cloud IP ranges -- including GitHub
    # Actions runners -- regardless of request headers. This isn't a code bug
    # (README already documents Stooq as cross-check-only, "can break without
    # notice"), so a failure here skips with a clear reason instead of failing
    # the whole CI job; if Stooq's blocking status ever changes, this starts
    # asserting real data again automatically.
    try:
        df = StooqSource().fetch(["SPY"], RECENT_START, RECENT_END)
    except DataSourceError as exc:
        pytest.skip(f"stooq did not return usable data (likely bot-blocking this runner's IP): {exc}")
    assert not df.empty
    assert (df["symbol"] == "SPY").all()


def test_coingecko_live_fetch() -> None:
    df = CoinGeckoSource().fetch(["BTC-USD"], RECENT_START, RECENT_END)
    assert not df.empty
    assert df["close"].notna().any()


@pytest.mark.skipif(not os.environ.get("FRED_API_KEY"), reason="FRED_API_KEY not set")
def test_fred_live_fetch() -> None:
    df = FredSource().fetch(["FEDFUNDS"], RECENT_START - timedelta(days=180), RECENT_END)
    assert not df.empty
    assert (df["series_id"] == "FEDFUNDS").all()


@pytest.mark.skipif(not os.environ.get("ALPHAVANTAGE_API_KEY"), reason="ALPHAVANTAGE_API_KEY not set")
def test_alpha_vantage_live_fetch() -> None:
    df = AlphaVantageSource().fetch(["SPY"], RECENT_START, RECENT_END)
    assert not df.empty


@pytest.mark.skipif(not os.environ.get("NASDAQ_DATA_LINK_API_KEY"), reason="NASDAQ_DATA_LINK_API_KEY not set")
def test_nasdaq_data_link_live_fetch() -> None:
    df = NasdaqDataLinkSource().fetch(["LBMA/GOLD"], RECENT_START - timedelta(days=30), RECENT_END)
    assert not df.empty


@pytest.mark.skipif(not os.environ.get("SEC_EDGAR_USER_AGENT"), reason="SEC_EDGAR_USER_AGENT not set")
def test_sec_edgar_live_fetch() -> None:
    df = SecEdgarSource().fetch(["AAPL"], ["Assets"], date(2015, 1, 1), RECENT_END)
    assert not df.empty
    assert (df["symbol"] == "AAPL").all()
