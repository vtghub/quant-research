from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant_research.core.exceptions import ConfigError
from quant_research.core.registries import STRATEGY_REGISTRY
from quant_research.strategy.library.risk_parity import RiskParityStrategy


def test_registered() -> None:
    assert "risk_parity" in STRATEGY_REGISTRY


def test_requires_prices() -> None:
    strategy = RiskParityStrategy()
    with pytest.raises(ConfigError, match="requires prices"):
        strategy.generate_weights(pd.DataFrame({"AAA": [1.0]}), prices=None)


@pytest.fixture
def prices() -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=60)
    rng = np.random.default_rng(15)
    calm = 100 * (1 + rng.normal(0, 0.005, 60)).cumprod()
    volatile = 100 * (1 + rng.normal(0, 0.05, 60)).cumprod()
    return pd.DataFrame({"CALM": calm, "VOL": volatile}, index=dates)


def test_lower_vol_asset_gets_higher_weight(prices: pd.DataFrame) -> None:
    signal_df = pd.DataFrame(1.0, index=prices.index, columns=prices.columns)  # everything eligible
    strategy = RiskParityStrategy(vol_lookback=20, require_positive_signal=False)
    weights = strategy.generate_weights(signal_df, prices)

    tail = weights.iloc[-1]
    assert tail["CALM"] > tail["VOL"]


def test_gross_exposure_is_one_when_fully_eligible(prices: pd.DataFrame) -> None:
    signal_df = pd.DataFrame(1.0, index=prices.index, columns=prices.columns)
    strategy = RiskParityStrategy(vol_lookback=20, require_positive_signal=False)
    weights = strategy.generate_weights(signal_df, prices)

    tail_gross = weights.iloc[-5:].abs().sum(axis=1)
    assert np.allclose(tail_gross, 1.0)


def test_negative_signal_excludes_symbol_when_required(prices: pd.DataFrame) -> None:
    signal_df = pd.DataFrame({"CALM": 1.0, "VOL": -1.0}, index=prices.index)
    strategy = RiskParityStrategy(vol_lookback=20, require_positive_signal=True)
    weights = strategy.generate_weights(signal_df, prices)

    assert np.allclose(weights["VOL"].iloc[-5:], 0.0)
    assert np.allclose(weights["CALM"].iloc[-5:], 1.0)
