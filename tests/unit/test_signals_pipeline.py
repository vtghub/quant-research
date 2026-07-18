from __future__ import annotations

import pandas as pd
import pytest

from quant_research.config.schema import SignalConfig
from quant_research.core.exceptions import ConfigError
from quant_research.core.hooks import HookEvent, HookManager
from quant_research.core.registries import SIGNAL_REGISTRY
from quant_research.signals.base import Signal
from quant_research.signals.pipeline import compute_signals


@pytest.fixture(autouse=True)
def _register_test_signals():
    # Register lightweight throwaway signals for this test module only, cleaned up after.
    if "double" not in SIGNAL_REGISTRY:

        @SIGNAL_REGISTRY.register("double")
        class DoubleSignal(Signal):
            name = "double"

            def compute(self, prices, inputs=None):
                return prices * 2

        @SIGNAL_REGISTRY.register("sum_inputs")
        class SumInputsSignal(Signal):
            name = "sum_inputs"

            def compute(self, prices, inputs=None):
                frames = list((inputs or {}).values())
                out = frames[0].copy()
                for f in frames[1:]:
                    out = out + f
                return out

    yield
    SIGNAL_REGISTRY._items.pop("double", None)
    SIGNAL_REGISTRY._items.pop("sum_inputs", None)


def test_compute_signals_no_dependencies(synthetic_prices: pd.DataFrame) -> None:
    configs = [SignalConfig(name="double", alias="d")]
    results = compute_signals(synthetic_prices, configs)
    pd.testing.assert_frame_equal(results["d"], synthetic_prices * 2)


def test_compute_signals_resolves_dependencies_in_order(synthetic_prices: pd.DataFrame) -> None:
    configs = [
        SignalConfig(name="double", alias="d1"),
        SignalConfig(name="double", alias="d2"),
        SignalConfig(name="sum_inputs", alias="combo", depends_on=["d1", "d2"]),
    ]
    results = compute_signals(synthetic_prices, configs)
    expected = synthetic_prices * 2 + synthetic_prices * 2
    pd.testing.assert_frame_equal(results["combo"], expected)


def test_compute_signals_fires_hooks(synthetic_prices: pd.DataFrame) -> None:
    hooks = HookManager()
    events: list[str] = []
    hooks.register(HookEvent.BEFORE_SIGNAL, lambda ctx: events.append(f"before:{ctx.payload['alias']}"))
    hooks.register(HookEvent.AFTER_SIGNAL, lambda ctx: events.append(f"after:{ctx.payload['alias']}"))

    compute_signals(synthetic_prices, [SignalConfig(name="double", alias="d")], hooks)

    assert events == ["before:d", "after:d"]


def test_circular_dependency_raises() -> None:
    configs = [
        SignalConfig(name="sum_inputs", alias="a", depends_on=["b"]),
        SignalConfig(name="sum_inputs", alias="b", depends_on=["a"]),
    ]
    with pytest.raises(ConfigError, match="circular"):
        compute_signals(pd.DataFrame({"AAA": [1.0, 2.0]}), configs)
