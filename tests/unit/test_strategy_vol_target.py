from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant_research.core.exceptions import ConfigError
from quant_research.core.registries import STRATEGY_REGISTRY
from quant_research.strategy.vol_target import VolTargetedStrategy, apply_vol_target


def test_vol_targeted_is_registered() -> None:
    assert "vol_targeted" in STRATEGY_REGISTRY


@pytest.fixture
def prices() -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=120)
    rng = np.random.default_rng(21)
    return pd.DataFrame(
        {"AAA": 100.0 * (1 + rng.normal(0.0, 0.02, 120)).cumprod()}, index=dates
    )


def test_apply_vol_target_scales_toward_target(prices: pd.DataFrame) -> None:
    dates = prices.index
    weights = pd.DataFrame({"AAA": 1.0}, index=dates)  # always fully long, no scaling

    scaled = apply_vol_target(weights, prices, target_annual_vol=0.05, lookback=20, max_leverage=5.0)

    # realized portfolio vol under the *scaled* weights should track closer to
    # the target than the unscaled 100%-invested version for a volatile series
    unscaled_realized = (weights.shift(1).fillna(0.0) * prices.pct_change()).sum(axis=1)
    scaled_realized = (scaled.shift(1).fillna(0.0) * prices.pct_change()).sum(axis=1)
    unscaled_vol = unscaled_realized.iloc[40:].std(ddof=0) * np.sqrt(252)
    scaled_vol = scaled_realized.iloc[40:].std(ddof=0) * np.sqrt(252)
    assert scaled_vol < unscaled_vol


def test_apply_vol_target_respects_max_leverage(prices: pd.DataFrame) -> None:
    dates = prices.index
    weights = pd.DataFrame({"AAA": 0.01}, index=dates)  # tiny weight -> tiny realized vol -> huge scale needed
    scaled = apply_vol_target(weights, prices, target_annual_vol=1.0, lookback=20, max_leverage=2.0)
    assert (scaled.abs() <= 0.01 * 2.0 + 1e-9).all().all()


def test_vol_targeted_strategy_wraps_inner_strategy_by_name(prices: pd.DataFrame) -> None:
    dates = prices.index
    signal_df = pd.DataFrame({"AAA": np.linspace(-1, 1, len(dates))}, index=dates)

    # register a trivial inner strategy for this test
    from quant_research.strategy.base import Strategy

    if "always_long" not in STRATEGY_REGISTRY:

        @STRATEGY_REGISTRY.register("always_long")
        class _AlwaysLong(Strategy):
            name = "always_long"

            def generate_weights(self, signal_df, prices=None):
                return pd.DataFrame(1.0, index=signal_df.index, columns=signal_df.columns)

    strategy = VolTargetedStrategy(inner_strategy="always_long", target_annual_vol=0.05)
    weights = strategy.generate_weights(signal_df, prices)
    assert weights.shape == signal_df.shape
    STRATEGY_REGISTRY._items.pop("always_long", None)


def test_vol_targeted_requires_prices() -> None:
    strategy = VolTargetedStrategy(inner_strategy="rank_weighted_long_short")
    with pytest.raises(ConfigError, match="requires prices"):
        strategy.generate_weights(pd.DataFrame({"AAA": [1.0]}), prices=None)


def test_vol_targeted_requires_inner_strategy_param() -> None:
    strategy = VolTargetedStrategy()
    with pytest.raises(ConfigError, match="inner_strategy"):
        strategy.generate_weights(pd.DataFrame({"AAA": [1.0]}), prices=pd.DataFrame({"AAA": [100.0]}))
