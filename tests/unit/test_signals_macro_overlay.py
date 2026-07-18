from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant_research.core.exceptions import ConfigError
from quant_research.signals.library.macro_overlay import MacroOverlaySignal


def test_missing_inputs_raises_config_error() -> None:
    signal = MacroOverlaySignal()
    with pytest.raises(ConfigError, match="depends_on"):
        signal.compute(pd.DataFrame(), inputs=None)


def test_rising_macro_series_gives_positive_score_by_default() -> None:
    dates = pd.bdate_range("2020-01-01", periods=300)
    macro_level = np.linspace(0.0, 5.0, 300)
    macro_wide = pd.DataFrame({"A": macro_level, "B": macro_level}, index=dates)

    signal = MacroOverlaySignal(window=252)
    result = signal.compute(pd.DataFrame(), inputs={"macro_series": macro_wide})

    assert result["A"].iloc[-1] > 0
    # broadcast: every symbol column has the identical macro-derived score
    assert np.isclose(result["A"].iloc[-1], result["B"].iloc[-1])


def test_direction_param_flips_sign() -> None:
    dates = pd.bdate_range("2020-01-01", periods=300)
    macro_level = np.linspace(0.0, 5.0, 300)
    macro_wide = pd.DataFrame({"A": macro_level}, index=dates)

    positive = MacroOverlaySignal(window=252, direction=1.0).compute(pd.DataFrame(), inputs={"m": macro_wide})
    negative = MacroOverlaySignal(window=252, direction=-1.0).compute(pd.DataFrame(), inputs={"m": macro_wide})

    assert np.isclose(positive["A"].iloc[-1], -negative["A"].iloc[-1])
