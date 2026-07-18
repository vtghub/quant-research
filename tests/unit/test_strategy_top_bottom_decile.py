from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant_research.core.registries import STRATEGY_REGISTRY
from quant_research.strategy.library.top_bottom_decile import TopBottomDecileEqualWeight


def test_registered() -> None:
    assert "top_bottom_decile_ew" in STRATEGY_REGISTRY


@pytest.fixture
def signal_df() -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=2)
    # 10 symbols, clean decile spread
    return pd.DataFrame(
        {chr(65 + i): [10 - i, 10 - i] for i in range(10)}, index=dates, dtype=float
    )


def test_top_and_bottom_get_opposite_signs_and_middle_excluded(signal_df: pd.DataFrame) -> None:
    strategy = TopBottomDecileEqualWeight(n_quantiles=10)
    weights = strategy.generate_weights(signal_df)

    assert weights["A"].iloc[0] > 0  # highest signal -> long
    assert weights["J"].iloc[0] < 0  # lowest signal -> short
    assert np.isclose(weights["E"].iloc[0], 0.0)  # middle, excluded from both tails


def test_each_side_sums_to_half_gross(signal_df: pd.DataFrame) -> None:
    strategy = TopBottomDecileEqualWeight(n_quantiles=10)
    weights = strategy.generate_weights(signal_df)
    long_side = weights.where(weights > 0, 0.0).sum(axis=1)
    short_side = weights.where(weights < 0, 0.0).sum(axis=1)
    assert np.allclose(long_side, 0.5)
    assert np.allclose(short_side, -0.5)


def test_gross_exposure_is_one(signal_df: pd.DataFrame) -> None:
    strategy = TopBottomDecileEqualWeight(n_quantiles=10)
    weights = strategy.generate_weights(signal_df)
    assert np.allclose(weights.abs().sum(axis=1), 1.0)
