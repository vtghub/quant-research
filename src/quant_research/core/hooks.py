"""Event bus for cross-cutting pipeline extensions (logging, data-quality gates, alerting).

Distinct in purpose from the registry: hooks never replace core logic, they only
observe or react around it. A hook raising HookAbort deliberately halts the run;
any other exception raised by a hook is caught and logged so one broken observer
can't take down the pipeline.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from quant_research.core.exceptions import HookAbort

logger = logging.getLogger(__name__)


class HookEvent(str, Enum):
    BEFORE_FETCH = "before_fetch"
    AFTER_FETCH = "after_fetch"
    BEFORE_SIGNAL = "before_signal"
    AFTER_SIGNAL = "after_signal"
    BEFORE_BACKTEST = "before_backtest"
    AFTER_BACKTEST = "after_backtest"
    BEFORE_REPORT = "before_report"
    AFTER_REPORT = "after_report"


@dataclass
class HookContext:
    event: HookEvent
    payload: dict[str, Any] = field(default_factory=dict)


HookFn = Callable[[HookContext], None]


class HookManager:
    def __init__(self) -> None:
        self._handlers: dict[HookEvent, list[HookFn]] = {event: [] for event in HookEvent}

    def register(self, event: HookEvent, fn: HookFn) -> None:
        self._handlers[event].append(fn)

    def on(self, event: HookEvent) -> Callable[[HookFn], HookFn]:
        def decorator(fn: HookFn) -> HookFn:
            self.register(event, fn)
            return fn

        return decorator

    def fire(self, event: HookEvent, **payload: Any) -> HookContext:
        ctx = HookContext(event=event, payload=payload)
        for fn in self._handlers[event]:
            try:
                fn(ctx)
            except HookAbort:
                raise
            except Exception:
                logger.exception("hook %s raised for event %s", fn, event.value)
        return ctx

    def handler_count(self, event: HookEvent) -> int:
        return len(self._handlers[event])
