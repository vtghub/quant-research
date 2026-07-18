from __future__ import annotations

import pandas as pd

from quant_research.core.registries import UNIVERSE_PROVIDER_REGISTRY
from quant_research.universe.static import StaticUniverse


def test_registered() -> None:
    assert "static" in UNIVERSE_PROVIDER_REGISTRY
    assert UNIVERSE_PROVIDER_REGISTRY.get("static") is StaticUniverse


def test_all_symbols_ever_is_the_configured_list() -> None:
    provider = StaticUniverse(["AAA", "BBB"])
    assert provider.all_symbols_ever() == ["AAA", "BBB"]


def test_membership_mask_is_all_true() -> None:
    provider = StaticUniverse(["AAA", "BBB"])
    calendar = pd.bdate_range("2020-01-01", periods=10)
    mask = provider.membership_mask(calendar)
    assert mask.shape == (10, 2)
    assert mask.all().all()


def test_ignores_extra_kwargs() -> None:
    # Registry.create passes provider_params through unconditionally --
    # StaticUniverse must tolerate irrelevant kwargs meant for other providers.
    provider = StaticUniverse(["AAA"], membership_csv="/not/used.csv")
    assert provider.all_symbols_ever() == ["AAA"]
