from __future__ import annotations

import logging

from quant_research.core.hooks import HookContext, HookEvent, HookManager

logger = logging.getLogger("quant_research.pipeline")


def register(hooks: HookManager) -> None:
    @hooks.on(HookEvent.BEFORE_FETCH)
    def _before_fetch(ctx: HookContext) -> None:
        logger.info(
            "fetching %s from %s [%s..%s]",
            ctx.payload.get("symbol"),
            ctx.payload.get("source"),
            ctx.payload.get("start"),
            ctx.payload.get("end"),
        )

    @hooks.on(HookEvent.AFTER_FETCH)
    def _after_fetch(ctx: HookContext) -> None:
        df = ctx.payload.get("df")
        rows = len(df) if df is not None else 0
        logger.info("fetched %d rows for %s from %s", rows, ctx.payload.get("symbol"), ctx.payload.get("source"))

    @hooks.on(HookEvent.BEFORE_SIGNAL)
    def _before_signal(ctx: HookContext) -> None:
        logger.info("computing signal '%s' (%s)", ctx.payload.get("alias"), ctx.payload.get("name"))

    @hooks.on(HookEvent.BEFORE_BACKTEST)
    def _before_backtest(ctx: HookContext) -> None:
        logger.info("starting backtest")

    @hooks.on(HookEvent.AFTER_BACKTEST)
    def _after_backtest(ctx: HookContext) -> None:
        result = ctx.payload.get("result")
        if result is not None:
            logger.info(
                "backtest complete: sharpe=%.3f max_drawdown=%.3f",
                result.metrics.get("sharpe", float("nan")),
                result.metrics.get("max_drawdown", float("nan")),
            )

    @hooks.on(HookEvent.AFTER_REPORT)
    def _after_report(ctx: HookContext) -> None:
        paths = ctx.payload.get("paths") or []
        logger.info("report written: %s", ", ".join(str(p) for p in paths))
