from __future__ import annotations

import numpy as np
import pandas as pd

from quant_research.core.registries import SIGNAL_REGISTRY
from quant_research.signals.library.momentum import MomentumSignal


def test_momentum_is_registered() -> None:
    assert "momentum" in SIGNAL_REGISTRY
    assert SIGNAL_REGISTRY.get("momentum") is MomentumSignal


def test_momentum_matches_hand_computed_value() -> None:
    dates = pd.bdate_range("2020-01-01", periods=200)
    # deterministic geometric growth so momentum has a known closed form
    prices = pd.DataFrame({"AAA": 100.0 * (1.001 ** np.arange(200))}, index=dates)

    signal = MomentumSignal(lookback=50, skip_recent=10)
    result = signal.compute(prices)

    t = 150
    expected = prices["AAA"].iloc[t - 10] / prices["AAA"].iloc[t - 10 - 50] - 1.0
    assert np.isclose(result["AAA"].iloc[t], expected)


def test_momentum_warmup_is_nan_not_error() -> None:
    dates = pd.bdate_range("2020-01-01", periods=30)
    prices = pd.DataFrame({"AAA": np.linspace(100, 110, 30)}, index=dates)

    signal = MomentumSignal(lookback=20, skip_recent=5)
    result = signal.compute(prices)

    assert result["AAA"].iloc[:25].isna().all()
    assert result["AAA"].iloc[25:].notna().all()


def test_momentum_positive_for_uptrend() -> None:
    dates = pd.bdate_range("2020-01-01", periods=200)
    prices = pd.DataFrame({"UP": np.linspace(100, 200, 200), "DOWN": np.linspace(200, 100, 200)}, index=dates)

    signal = MomentumSignal(lookback=100, skip_recent=5)
    result = signal.compute(prices)

    assert (result["UP"].iloc[150:] > 0).all()
    assert (result["DOWN"].iloc[150:] < 0).all()
