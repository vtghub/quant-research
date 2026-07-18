from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant_research.core.exceptions import ConfigError
from quant_research.signals.library.cross_sectional_rank import CrossSectionalRankSignal


def test_ranks_map_to_minus1_to_1() -> None:
    dates = pd.bdate_range("2020-01-01", periods=2)
    base = pd.DataFrame({"A": [5, 5], "B": [4, 4], "C": [3, 3], "D": [2, 2], "E": [1, 1]}, index=dates, dtype=float)
    signal = CrossSectionalRankSignal()
    result = signal.compute(pd.DataFrame(), inputs={"mom": base})

    assert np.isclose(result["A"].iloc[0], 1.0)  # highest value -> top percentile -> score 1.0
    assert np.isclose(result["E"].iloc[0], -0.6)  # lowest of 5 -> pct rank 0.2 -> 2*0.2-1
    assert result["A"].iloc[0] > result["B"].iloc[0] > result["C"].iloc[0]


def test_missing_inputs_raises_config_error() -> None:
    signal = CrossSectionalRankSignal()
    with pytest.raises(ConfigError, match="depends_on"):
        signal.compute(pd.DataFrame(), inputs=None)


def test_explicit_source_param_selects_alias() -> None:
    dates = pd.bdate_range("2020-01-01", periods=1)
    a = pd.DataFrame({"X": [1.0], "Y": [2.0]}, index=dates)
    b = pd.DataFrame({"X": [2.0], "Y": [1.0]}, index=dates)
    signal = CrossSectionalRankSignal(source="b")
    result = signal.compute(pd.DataFrame(), inputs={"a": a, "b": b})
    assert result["X"].iloc[0] > result["Y"].iloc[0]  # ranked using b, where X > Y
