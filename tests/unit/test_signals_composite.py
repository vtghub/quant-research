from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant_research.core.exceptions import ConfigError
from quant_research.signals.library.composite import CompositeSignal


def test_missing_inputs_raises_config_error() -> None:
    signal = CompositeSignal()
    with pytest.raises(ConfigError, match="depends_on"):
        signal.compute(pd.DataFrame(), inputs=None)


def test_equal_weight_average_of_two_identical_signals_equals_zscore() -> None:
    dates = pd.bdate_range("2020-01-01", periods=3)
    a = pd.DataFrame({"X": [1.0, 2.0, 3.0], "Y": [3.0, 2.0, 1.0]}, index=dates)
    signal = CompositeSignal()
    combined = signal.compute(pd.DataFrame(), inputs={"a": a, "b": a})

    row_mean = a.mean(axis=1)
    row_std = a.std(axis=1, ddof=0)
    expected_z = a.sub(row_mean, axis=0).div(row_std, axis=0)
    pd.testing.assert_frame_equal(combined, expected_z)


def test_weights_param_changes_relative_contribution() -> None:
    dates = pd.bdate_range("2020-01-01", periods=3)
    a = pd.DataFrame({"X": [1.0, 2.0, 3.0], "Y": [3.0, 2.0, 1.0]}, index=dates)
    b = pd.DataFrame({"X": [3.0, 2.0, 1.0], "Y": [1.0, 2.0, 3.0]}, index=dates)  # inverse of a

    heavy_a = CompositeSignal(weights={"a": 10.0, "b": 1.0}).compute(pd.DataFrame(), inputs={"a": a, "b": b})
    heavy_b = CompositeSignal(weights={"a": 1.0, "b": 10.0}).compute(pd.DataFrame(), inputs={"a": a, "b": b})

    # a and b are perfect opposites, so heavily-weighting one vs the other should
    # flip the sign of the combined score
    assert np.sign(heavy_a["X"].iloc[0]) == -np.sign(heavy_b["X"].iloc[0])
