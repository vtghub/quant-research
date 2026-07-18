from __future__ import annotations

import numpy as np
import pandas as pd

from quant_research.signals.library.bollinger import BollingerZSignal


def test_bollinger_z_is_zero_for_flat_price() -> None:
    dates = pd.bdate_range("2020-01-01", periods=40)
    prices = pd.DataFrame({"AAA": [100.0] * 40}, index=dates)
    signal = BollingerZSignal(window=20)
    result = signal.compute(prices)
    # zero std -> 0/0 NaN is acceptable, but if not NaN it must be ~0
    tail = result["AAA"].iloc[25:]
    assert tail.isna().all() or np.allclose(tail.dropna(), 0.0, atol=1e-9)


def test_bollinger_z_scaled_by_num_std() -> None:
    rng = np.random.default_rng(3)
    dates = pd.bdate_range("2020-01-01", periods=100)
    prices = pd.DataFrame({"AAA": 100 + rng.normal(0, 1, 100).cumsum()}, index=dates)

    narrow = BollingerZSignal(window=20, num_std=1.0).compute(prices)
    wide = BollingerZSignal(window=20, num_std=4.0).compute(prices)
    # same underlying z, just divided by a larger num_std -> smaller magnitude
    ratio = (narrow["AAA"] / wide["AAA"]).dropna()
    assert np.allclose(ratio, 4.0, atol=1e-6)


def test_bollinger_extreme_price_gives_large_magnitude_score() -> None:
    dates = pd.bdate_range("2020-01-01", periods=25)
    values = [100.0] * 20 + [100.0, 100.0, 100.0, 100.0, 200.0]
    prices = pd.DataFrame({"AAA": values}, index=dates)
    signal = BollingerZSignal(window=20, num_std=2.0)
    result = signal.compute(prices)
    assert result["AAA"].iloc[-1] > 1.0
