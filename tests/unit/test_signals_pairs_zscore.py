from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant_research.core.exceptions import ConfigError
from quant_research.signals.library.pairs_zscore import PairsZScoreSignal


def test_missing_pairs_param_raises() -> None:
    signal = PairsZScoreSignal()
    with pytest.raises(ConfigError, match="params.pairs"):
        signal.compute(pd.DataFrame({"AAA": [1.0]}))


def test_unknown_symbol_in_pair_raises() -> None:
    dates = pd.bdate_range("2020-01-01", periods=5)
    prices = pd.DataFrame({"AAA": [100.0] * 5, "BBB": [50.0] * 5}, index=dates)
    signal = PairsZScoreSignal(pairs=[["AAA", "ZZZ"]])
    with pytest.raises(ConfigError, match="not in the universe"):
        signal.compute(prices)


def test_unpaired_symbol_gets_nan() -> None:
    dates = pd.bdate_range("2020-01-01", periods=80)
    rng = np.random.default_rng(30)
    prices = pd.DataFrame(
        {
            "AAA": 100 * (1 + rng.normal(0, 0.01, 80)).cumprod(),
            "BBB": 50 * (1 + rng.normal(0, 0.01, 80)).cumprod(),
            "CCC": 20 * (1 + rng.normal(0, 0.01, 80)).cumprod(),
        },
        index=dates,
    )
    signal = PairsZScoreSignal(pairs=[["AAA", "BBB"]], window=20)
    result = signal.compute(prices)
    assert result["CCC"].isna().all()
    assert result["AAA"].dropna().shape[0] > 0


def test_pair_legs_are_opposite_sign() -> None:
    dates = pd.bdate_range("2020-01-01", periods=80)
    # AAA drifts up relative to BBB -> spread widens -> nonzero z late in the window
    aaa = 100 * np.linspace(1.0, 1.5, 80)
    bbb = 100 * np.ones(80)
    prices = pd.DataFrame({"AAA": aaa, "BBB": bbb}, index=dates)

    signal = PairsZScoreSignal(pairs=[["AAA", "BBB"]], window=20)
    result = signal.compute(prices)

    tail = result.dropna().iloc[-1]
    assert np.isclose(tail["AAA"], -tail["BBB"])
    # AAA has richened relative to BBB -> short AAA (negative), long BBB (positive)
    assert tail["AAA"] < 0
    assert tail["BBB"] > 0
