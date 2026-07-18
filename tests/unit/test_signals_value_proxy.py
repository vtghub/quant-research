from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant_research.core.exceptions import ConfigError
from quant_research.signals.library.value_proxy import ValueProxySignal


def test_missing_inputs_raises_config_error() -> None:
    signal = ValueProxySignal()
    with pytest.raises(ConfigError, match="depends_on"):
        signal.compute(pd.DataFrame({"AAA": [1.0]}), inputs=None)


def test_ratio_is_fundamentals_over_price() -> None:
    dates = pd.bdate_range("2020-01-01", periods=3)
    prices = pd.DataFrame({"AAA": [10.0, 20.0, 50.0]}, index=dates)
    eps = pd.DataFrame({"AAA": [1.0, 1.0, 1.0]}, index=dates)

    signal = ValueProxySignal()
    result = signal.compute(prices, inputs={"fundamentals_eps": eps})

    # cheaper price for the same earnings -> higher earnings yield -> higher score
    assert result["AAA"].iloc[0] > result["AAA"].iloc[1] > result["AAA"].iloc[2]
    assert np.isclose(result["AAA"].iloc[0], 0.1)


def test_direction_param_flips_sign() -> None:
    dates = pd.bdate_range("2020-01-01", periods=1)
    prices = pd.DataFrame({"AAA": [10.0]}, index=dates)
    concept = pd.DataFrame({"AAA": [2.0]}, index=dates)

    positive = ValueProxySignal(direction=1.0).compute(prices, inputs={"c": concept})
    negative = ValueProxySignal(direction=-1.0).compute(prices, inputs={"c": concept})
    assert np.isclose(positive["AAA"].iloc[0], -negative["AAA"].iloc[0])
