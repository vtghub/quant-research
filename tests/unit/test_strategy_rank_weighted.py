from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant_research.core.registries import STRATEGY_REGISTRY
from quant_research.strategy.library.rank_weighted import RankWeightedLongShort


def test_registered() -> None:
    assert "rank_weighted_long_short" in STRATEGY_REGISTRY
    assert STRATEGY_REGISTRY.get("rank_weighted_long_short") is RankWeightedLongShort


@pytest.fixture
def signal_df() -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=3)
    # 5 symbols, clean rank order: A highest .. E lowest, same every day
    return pd.DataFrame(
        {"A": [5, 5, 5], "B": [4, 4, 4], "C": [3, 3, 3], "D": [2, 2, 2], "E": [1, 1, 1]},
        index=dates,
        dtype=float,
    )


def test_top_and_bottom_get_opposite_sign_weights(signal_df: pd.DataFrame) -> None:
    strategy = RankWeightedLongShort(top_frac=0.3, bottom_frac=0.3)
    weights = strategy.generate_weights(signal_df)

    assert (weights["A"] > 0).all()  # top-ranked -> long
    assert (weights["E"] < 0).all()  # bottom-ranked -> short
    assert (weights["C"] == 0).all()  # middle, excluded from both tails


def test_gross_exposure_is_one(signal_df: pd.DataFrame) -> None:
    strategy = RankWeightedLongShort(top_frac=0.4, bottom_frac=0.4)
    weights = strategy.generate_weights(signal_df)
    gross = weights.abs().sum(axis=1)
    assert np.allclose(gross, 1.0)


def test_dollar_neutral(signal_df: pd.DataFrame) -> None:
    strategy = RankWeightedLongShort(top_frac=0.4, bottom_frac=0.4)
    weights = strategy.generate_weights(signal_df)
    net = weights.sum(axis=1)
    assert np.allclose(net, 0.0, atol=1e-9)


def test_all_nan_row_yields_zero_weights() -> None:
    dates = pd.bdate_range("2020-01-01", periods=1)
    signal_df = pd.DataFrame({"A": [np.nan], "B": [np.nan]}, index=dates)
    strategy = RankWeightedLongShort()
    weights = strategy.generate_weights(signal_df)
    assert (weights.fillna(0.0) == 0.0).all().all()
