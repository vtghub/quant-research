from __future__ import annotations

import os
from datetime import date
from typing import Sequence

import pandas as pd
import requests

from quant_research.core.exceptions import DataSourceError
from quant_research.core.registries import FUNDAMENTALS_SOURCE_REGISTRY
from quant_research.data.base import FundamentalsDataSource, normalize_fundamentals

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
CONCEPT_URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json"

DEFAULT_CONCEPTS = ["Assets", "StockholdersEquity", "NetIncomeLoss", "EarningsPerShareBasic"]


@FUNDAMENTALS_SOURCE_REGISTRY.register("sec_edgar")
class SecEdgarSource(FundamentalsDataSource):
    """Free, no-key fundamentals from SEC EDGAR's XBRL company-concept API (e.g.
    Assets, StockholdersEquity, NetIncomeLoss, EarningsPerShareBasic -- any
    us-gaap tag a filer reports). SEC's fair-use policy requires a descriptive
    User-Agent identifying the requester (name + contact email); pass one
    explicitly or set SEC_EDGAR_USER_AGENT, or requests will be rejected."""

    name = "sec_edgar"

    def __init__(self, user_agent: str | None = None) -> None:
        self.user_agent = user_agent or os.environ.get("SEC_EDGAR_USER_AGENT")
        self._ticker_to_cik: dict[str, str] | None = None

    def _headers(self) -> dict[str, str]:
        if not self.user_agent:
            raise DataSourceError(
                "SEC EDGAR requires a descriptive User-Agent (e.g. 'Your Name your@email.com'). "
                "Pass user_agent= explicitly or set the SEC_EDGAR_USER_AGENT env var."
            )
        return {"User-Agent": self.user_agent}

    def _load_ticker_map(self) -> dict[str, str]:
        if self._ticker_to_cik is not None:
            return self._ticker_to_cik
        try:
            response = requests.get(TICKER_MAP_URL, headers=self._headers(), timeout=30)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise DataSourceError(f"sec_edgar failed to fetch ticker->CIK map: {exc}") from exc

        self._ticker_to_cik = {
            row["ticker"].upper(): f"{row['cik_str']:010d}" for row in payload.values()
        }
        return self._ticker_to_cik

    def _cik_for(self, symbol: str) -> str:
        ticker_map = self._load_ticker_map()
        try:
            return ticker_map[symbol.upper()]
        except KeyError:
            raise DataSourceError(f"sec_edgar: no CIK found for ticker '{symbol}'") from None

    def fetch(self, symbols: Sequence[str], concepts: Sequence[str], start: date, end: date) -> pd.DataFrame:
        start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
        frames = []
        for symbol in symbols:
            cik = self._cik_for(symbol)
            for concept in concepts:
                frames.append(self._fetch_concept(symbol, cik, concept, start_ts, end_ts))

        combined = pd.concat(frames, ignore_index=True)
        if combined.empty:
            raise DataSourceError(
                f"sec_edgar returned no data for {list(symbols)} / {list(concepts)} [{start}..{end}]"
            )
        return normalize_fundamentals(combined, self.name)

    def _fetch_concept(self, symbol: str, cik: str, concept: str, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> pd.DataFrame:
        url = CONCEPT_URL.format(cik=cik, concept=concept)
        try:
            response = requests.get(url, headers=self._headers(), timeout=30)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise DataSourceError(f"sec_edgar fetch failed for {symbol}/{concept}: {exc}") from exc

        rows = []
        for unit_facts in payload.get("units", {}).values():
            for fact in unit_facts:
                end = pd.Timestamp(fact.get("end"))
                if start_ts <= end <= end_ts:
                    rows.append({"date": end, "symbol": symbol, "concept": concept, "value": fact.get("val")})

        if not rows:
            return pd.DataFrame(columns=["date", "symbol", "concept", "value"])

        # a period end can be reported by multiple filings (10-Q then later
        # amended); keep the last-seen (most recently filed) value per date.
        return pd.DataFrame(rows).drop_duplicates(subset=["date"], keep="last")
