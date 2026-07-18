from __future__ import annotations

import textwrap

import pandas as pd
import pytest

from quant_research.core.exceptions import ConfigError
from quant_research.core.registries import UNIVERSE_PROVIDER_REGISTRY
from quant_research.universe.base import MembershipRecord
from quant_research.universe.point_in_time import PointInTimeUniverse, load_membership_csv


def test_registered() -> None:
    assert "point_in_time" in UNIVERSE_PROVIDER_REGISTRY
    assert UNIVERSE_PROVIDER_REGISTRY.get("point_in_time") is PointInTimeUniverse


def test_requires_csv_or_records() -> None:
    with pytest.raises(ConfigError, match="membership_csv= or records="):
        PointInTimeUniverse()


def test_all_symbols_ever_is_union_of_records() -> None:
    records = [
        MembershipRecord("AAA", pd.Timestamp("2020-01-01"), None),
        MembershipRecord("BBB", pd.Timestamp("2019-01-01"), pd.Timestamp("2020-06-01")),
    ]
    provider = PointInTimeUniverse(records=records)
    assert provider.all_symbols_ever() == ["AAA", "BBB"]


def test_membership_mask_respects_windows() -> None:
    records = [
        MembershipRecord("AAA", pd.Timestamp("2020-01-01"), None),  # still active
        MembershipRecord("BBB", pd.Timestamp("2020-01-01"), pd.Timestamp("2020-02-14")),  # removed mid-Feb
    ]
    provider = PointInTimeUniverse(records=records)
    calendar = pd.bdate_range("2020-01-01", "2020-03-01")
    mask = provider.membership_mask(calendar)

    assert mask.loc[pd.Timestamp("2020-01-15"), "AAA"]
    assert mask.loc[pd.Timestamp("2020-01-15"), "BBB"]
    assert mask.loc[pd.Timestamp("2020-02-28"), "AAA"]
    assert not mask.loc[pd.Timestamp("2020-02-28"), "BBB"]  # BBB was removed by then


def test_symbol_readded_after_removal_has_two_active_windows() -> None:
    records = [
        MembershipRecord("AAA", pd.Timestamp("2020-01-01"), pd.Timestamp("2020-01-31")),
        MembershipRecord("AAA", pd.Timestamp("2020-03-01"), None),
    ]
    provider = PointInTimeUniverse(records=records)
    calendar = pd.bdate_range("2020-01-01", "2020-04-01")
    mask = provider.membership_mask(calendar)

    assert mask.loc[pd.Timestamp("2020-01-15"), "AAA"]  # first window
    assert not mask.loc[pd.Timestamp("2020-02-14"), "AAA"]  # the gap between windows
    assert mask.loc[pd.Timestamp("2020-03-16"), "AAA"]  # re-added window


def test_load_membership_csv_parses_open_and_closed_windows(tmp_path) -> None:
    csv_text = textwrap.dedent(
        """
        symbol,start_date,end_date
        AAA,2019-01-01,
        BBB,2019-01-01,2020-06-01
        """
    ).strip()
    path = tmp_path / "membership.csv"
    path.write_text(csv_text)

    records = load_membership_csv(path)
    by_symbol = {r.symbol: r for r in records}
    assert by_symbol["AAA"].end_date is None
    assert by_symbol["BBB"].end_date == pd.Timestamp("2020-06-01")


def test_load_membership_csv_missing_file_raises() -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_membership_csv("/nonexistent/path.csv")


def test_load_membership_csv_missing_column_raises(tmp_path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("symbol\nAAA\n")
    with pytest.raises(ConfigError, match="missing required column"):
        load_membership_csv(path)


def test_point_in_time_universe_from_csv(tmp_path) -> None:
    csv_text = "symbol,start_date,end_date\nAAA,2020-01-01,\n"
    path = tmp_path / "membership.csv"
    path.write_text(csv_text)

    provider = PointInTimeUniverse(membership_csv=path)
    assert provider.all_symbols_ever() == ["AAA"]
