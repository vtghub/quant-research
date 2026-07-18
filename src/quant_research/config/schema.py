"""Pydantic models for the declarative pipeline config (YAML -> PipelineConfig)."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class UniverseConfig(BaseModel):
    symbols: list[str] = Field(default_factory=list)  # required for provider="static"; unused otherwise
    asset_class: Literal["equity", "etf", "fx", "crypto"] = "etf"
    start: date
    end: date
    interval: str = "1d"
    primary_source: str
    fallback_sources: list[str] = Field(default_factory=list)
    price_field: Literal["adj_close", "close"] = "adj_close"
    provider: str = "static"
    provider_params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_date_order(self) -> "UniverseConfig":
        if self.start >= self.end:
            raise ValueError(f"universe.start ({self.start}) must be before universe.end ({self.end})")
        return self

    @model_validator(mode="after")
    def _check_static_provider_has_symbols(self) -> "UniverseConfig":
        if self.provider == "static" and not self.symbols:
            raise ValueError("universe.symbols is required when universe.provider is 'static'")
        return self


class MacroConfig(BaseModel):
    series_ids: list[str] = Field(default_factory=list)
    source: str = "fred"


class FundamentalsConfig(BaseModel):
    concepts: list[str] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)  # empty -> use universe.symbols
    source: str = "sec_edgar"


class CacheConfig(BaseModel):
    backend: str = "parquet"
    root_dir: Path = Path(".cache/quant_research")
    params: dict[str, Any] = Field(default_factory=dict)


class SignalConfig(BaseModel):
    name: str
    alias: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)

    @property
    def resolved_alias(self) -> str:
        return self.alias or self.name


class ICAnalysisConfig(BaseModel):
    enabled: bool = True
    horizons: list[int] = Field(default_factory=lambda: [1, 5, 21, 63])
    n_quantiles: int = 5


class CostModelConfig(BaseModel):
    name: str = "bps"
    bps_per_trade: float = 5.0


class BacktestConfig(BaseModel):
    initial_capital: float = 1_000_000
    cost_model: CostModelConfig = Field(default_factory=CostModelConfig)
    rebalance: Literal["daily", "weekly", "monthly"] = "daily"


class StrategyConfig(BaseModel):
    name: str
    signals: list[str]
    params: dict[str, Any] = Field(default_factory=dict)


class ReportConfig(BaseModel):
    output_dir: Path = Path("reports")
    formats: list[Literal["markdown", "png"]] = Field(default_factory=lambda: ["markdown", "png"])


class HooksConfig(BaseModel):
    modules: list[str] = Field(default_factory=list)


class PipelineConfig(BaseModel):
    name: str
    universe: UniverseConfig
    macro: MacroConfig = Field(default_factory=MacroConfig)
    fundamentals: FundamentalsConfig = Field(default_factory=FundamentalsConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    signals: list[SignalConfig] = Field(default_factory=list)
    ic_analysis: ICAnalysisConfig = Field(default_factory=ICAnalysisConfig)
    strategy: StrategyConfig
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    report: ReportConfig = Field(default_factory=ReportConfig)
    hooks: HooksConfig = Field(default_factory=HooksConfig)

    @model_validator(mode="after")
    def _check_references_exist(self) -> "PipelineConfig":
        known_aliases = {s.resolved_alias for s in self.signals}
        dup_aliases = [a for a in known_aliases if [s.resolved_alias for s in self.signals].count(a) > 1]
        if dup_aliases:
            raise ValueError(f"duplicate signal alias(es): {sorted(set(dup_aliases))}")

        # Macro series and fundamentals concepts are fetched and reshaped onto the
        # price calendar at pipeline runtime (see Pipeline._load_macro_inputs /
        # _load_fundamentals_inputs), under aliases "macro_<series_id>" /
        # "fundamentals_<concept>" -- not configured Signals, but valid
        # depends_on targets.
        macro_aliases = {f"macro_{series_id}" for series_id in self.macro.series_ids}
        fundamentals_aliases = {f"fundamentals_{concept}" for concept in self.fundamentals.concepts}
        depends_on_targets = known_aliases | macro_aliases | fundamentals_aliases

        for signal in self.signals:
            for dep in signal.depends_on:
                if dep not in depends_on_targets:
                    raise ValueError(
                        f"signal '{signal.resolved_alias}' depends_on unknown signal/macro alias '{dep}'. "
                        f"Known: {sorted(depends_on_targets)}"
                    )

        for ref in self.strategy.signals:
            if ref not in known_aliases:
                raise ValueError(
                    f"strategy.signals references unknown signal alias '{ref}'. "
                    f"Known aliases: {sorted(known_aliases)}"
                )
        return self
