from __future__ import annotations

import logging

from quant_research.core.exceptions import HookAbort
from quant_research.core.hooks import HookContext, HookEvent, HookManager

logger = logging.getLogger("quant_research.data_quality")


def register(hooks: HookManager, max_null_frac: float = 0.05, max_gap_days: int = 7) -> None:
    """A concrete example of a data-quality gate: abort the run if a fetched
    symbol is mostly missing closes, and warn (without aborting) on large gaps."""

    @hooks.on(HookEvent.AFTER_FETCH)
    def _check(ctx: HookContext) -> None:
        df = ctx.payload.get("df")
        if df is None or df.empty or "close" not in df.columns:
            return

        null_frac = df["close"].isna().mean()
        if null_frac > max_null_frac:
            raise HookAbort(
                f"{ctx.payload.get('symbol')}: {null_frac:.1%} null closes from "
                f"{ctx.payload.get('source')} exceeds {max_null_frac:.0%} threshold"
            )

        gaps = df["date"].sort_values().diff().dt.days
        if (gaps > max_gap_days).any():
            logger.warning(
                "%s: gap > %d days in %s data", ctx.payload.get("symbol"), max_gap_days, ctx.payload.get("source")
            )
