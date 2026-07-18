from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant_research.core.exceptions import ConfigError
from quant_research.core.registries import STRATEGY_REGISTRY
from quant_research.strategy.library.min_variance import MinVarianceStrategy, _solve_min_variance


def test_registered() -> None:
    assert "min_variance" in STRATEGY_REGISTRY


def test_requires_prices() -> None:
    strategy = MinVarianceStrategy()
    with pytest.raises(ConfigError, match="requires prices"):
        strategy.generate_weights(pd.DataFrame({"AAA": [1.0]}), prices=None)


def test_solve_min_variance_favors_lower_variance_asset() -> None:
    cov = np.array([[0.0001, 0.0], [0.0, 0.01]])  # asset 0 much calmer than asset 1
    w = _solve_min_variance(cov)
    assert w is not None
    assert w[0] > w[1]
    assert np.isclose(w.sum(), 1.0)
    assert (w >= -1e-9).all()


@pytest.fixture
def prices() -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=100)
    rng = np.random.default_rng(16)
    calm = 100 * (1 + rng.normal(0, 0.003, 100)).cumprod()
    volatile = 100 * (1 + rng.normal(0, 0.04, 100)).cumprod()
    return pd.DataFrame({"CALM": calm, "VOL": volatile}, index=dates)


def test_generate_weights_favors_lower_vol_asset(prices: pd.DataFrame) -> None:
    signal_df = pd.DataFrame(1.0, index=prices.index, columns=prices.columns)
    strategy = MinVarianceStrategy(lookback=60, require_positive_signal=False)
    weights = strategy.generate_weights(signal_df, prices)

    tail = weights.iloc[-1]
    assert np.isclose(tail.sum(), 1.0, atol=1e-6)
    assert tail["CALM"] > tail["VOL"]


def test_negative_signal_excludes_symbol_when_required(prices: pd.DataFrame) -> None:
    signal_df = pd.DataFrame({"CALM": 1.0, "VOL": -1.0}, index=prices.index)
    strategy = MinVarianceStrategy(lookback=60, require_positive_signal=True)
    weights = strategy.generate_weights(signal_df, prices)

    # only one eligible symbol most days -> falls back to skipping (needs >=2)
    assert (weights["VOL"] == 0.0).all()


def test_warmup_period_has_zero_weights(prices: pd.DataFrame) -> None:
    signal_df = pd.DataFrame(1.0, index=prices.index, columns=prices.columns)
    strategy = MinVarianceStrategy(lookback=60, require_positive_signal=False)
    weights = strategy.generate_weights(signal_df, prices)
    assert (weights.iloc[:60] == 0.0).all().all()
