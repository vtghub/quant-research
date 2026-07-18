from __future__ import annotations

import pytest

from quant_research.core.exceptions import HookAbort
from quant_research.core.hooks import HookContext, HookEvent, HookManager


def test_register_and_fire_calls_handler_with_payload() -> None:
    hooks = HookManager()
    seen: list[HookContext] = []
    hooks.register(HookEvent.AFTER_FETCH, seen.append)

    hooks.fire(HookEvent.AFTER_FETCH, symbol="AAA", rows=10)

    assert len(seen) == 1
    assert seen[0].event is HookEvent.AFTER_FETCH
    assert seen[0].payload == {"symbol": "AAA", "rows": 10}


def test_decorator_form_registers() -> None:
    hooks = HookManager()
    calls = []

    @hooks.on(HookEvent.BEFORE_SIGNAL)
    def _handler(ctx: HookContext) -> None:
        calls.append(ctx.payload)

    hooks.fire(HookEvent.BEFORE_SIGNAL, alias="mom")
    assert calls == [{"alias": "mom"}]


def test_handlers_fire_in_registration_order() -> None:
    hooks = HookManager()
    order: list[str] = []
    hooks.register(HookEvent.AFTER_SIGNAL, lambda ctx: order.append("first"))
    hooks.register(HookEvent.AFTER_SIGNAL, lambda ctx: order.append("second"))

    hooks.fire(HookEvent.AFTER_SIGNAL)

    assert order == ["first", "second"]


def test_hook_abort_propagates() -> None:
    hooks = HookManager()

    def _fails(ctx: HookContext) -> None:
        raise HookAbort("stop")

    hooks.register(HookEvent.AFTER_FETCH, _fails)

    with pytest.raises(HookAbort, match="stop"):
        hooks.fire(HookEvent.AFTER_FETCH)


def test_generic_exception_is_swallowed_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    hooks = HookManager()
    calls: list[str] = []

    def _broken(ctx: HookContext) -> None:
        raise ValueError("boom")

    def _still_runs(ctx: HookContext) -> None:
        calls.append("ran")

    hooks.register(HookEvent.AFTER_FETCH, _broken)
    hooks.register(HookEvent.AFTER_FETCH, _still_runs)

    with caplog.at_level("ERROR"):
        hooks.fire(HookEvent.AFTER_FETCH)

    assert calls == ["ran"]
    assert "boom" in caplog.text or "raised for event" in caplog.text
