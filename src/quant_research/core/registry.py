"""Generic name -> implementation registry, the "plug and play" swap mechanism.

Data sources, cache backends, signals, and strategies are each looked up by name
(driven by config strings) rather than imported directly, so a new implementation
is added by writing one file and applying a decorator -- no core code changes.
"""
from __future__ import annotations

from typing import Callable, Generic, TypeVar

from quant_research.core.exceptions import RegistryError

T = TypeVar("T")


class Registry(Generic[T]):
    def __init__(self, kind: str) -> None:
        self.kind = kind
        self._items: dict[str, type[T]] = {}

    def register(self, name: str) -> Callable[[type[T]], type[T]]:
        def decorator(cls: type[T]) -> type[T]:
            if name in self._items:
                raise RegistryError(
                    f"{self.kind} '{name}' is already registered to "
                    f"{self._items[name].__qualname__}"
                )
            self._items[name] = cls
            return cls

        return decorator

    def get(self, name: str) -> type[T]:
        try:
            return self._items[name]
        except KeyError:
            available = ", ".join(sorted(self._items)) or "<none registered>"
            raise RegistryError(
                f"unknown {self.kind} '{name}'. Available: {available}"
            ) from None

    def create(self, name: str, /, **kwargs: object) -> T:
        return self.get(name)(**kwargs)  # type: ignore[call-arg]

    def list(self) -> list[str]:
        return sorted(self._items)

    def __contains__(self, name: str) -> bool:
        return name in self._items
