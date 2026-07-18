from __future__ import annotations

import pytest

from quant_research.core.exceptions import RegistryError
from quant_research.core.registry import Registry


class Base:
    def __init__(self, value: int = 0) -> None:
        self.value = value


def test_register_and_create() -> None:
    reg: Registry[Base] = Registry("widget")

    @reg.register("thing")
    class Thing(Base):
        pass

    assert reg.list() == ["thing"]
    assert "thing" in reg
    instance = reg.create("thing", value=5)
    assert isinstance(instance, Thing)
    assert instance.value == 5


def test_duplicate_registration_raises() -> None:
    reg: Registry[Base] = Registry("widget")

    @reg.register("thing")
    class Thing(Base):
        pass

    with pytest.raises(RegistryError, match="already registered"):

        @reg.register("thing")
        class OtherThing(Base):
            pass


def test_unknown_name_raises_with_available_list() -> None:
    reg: Registry[Base] = Registry("widget")

    @reg.register("known")
    class Known(Base):
        pass

    with pytest.raises(RegistryError, match="unknown widget 'missing'.*known"):
        reg.get("missing")
