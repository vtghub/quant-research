from __future__ import annotations

import textwrap

import pytest
from pydantic import ValidationError

from quant_research.config.loader import load_config
from quant_research.config.schema import PipelineConfig
from quant_research.core.exceptions import ConfigError

MINIMAL = {
    "name": "test_pipeline",
    "universe": {
        "symbols": ["AAA", "BBB"],
        "start": "2020-01-01",
        "end": "2021-01-01",
        "primary_source": "yfinance",
    },
    "signals": [{"name": "momentum", "alias": "mom"}],
    "strategy": {"name": "rank_weighted_long_short", "signals": ["mom"]},
}


def test_minimal_config_parses_with_defaults() -> None:
    cfg = PipelineConfig(**MINIMAL)
    assert cfg.universe.asset_class == "etf"
    assert cfg.cache.backend == "parquet"
    assert cfg.backtest.cost_model.bps_per_trade == 5.0
    assert cfg.ic_analysis.horizons == [1, 5, 21, 63]


def test_start_after_end_rejected() -> None:
    bad = {**MINIMAL, "universe": {**MINIMAL["universe"], "start": "2022-01-01", "end": "2021-01-01"}}
    with pytest.raises(ValidationError, match="must be before"):
        PipelineConfig(**bad)


def test_strategy_referencing_unknown_signal_alias_rejected() -> None:
    bad = {**MINIMAL, "strategy": {"name": "rank_weighted_long_short", "signals": ["missing"]}}
    with pytest.raises(ValidationError, match="unknown signal alias"):
        PipelineConfig(**bad)


def test_signal_depends_on_unknown_alias_rejected() -> None:
    bad = dict(MINIMAL)
    bad["signals"] = [
        {"name": "momentum", "alias": "mom"},
        {"name": "composite", "alias": "combo", "depends_on": ["nope"]},
    ]
    with pytest.raises(ValidationError, match="depends_on unknown signal"):
        PipelineConfig(**bad)


def test_duplicate_alias_rejected() -> None:
    bad = dict(MINIMAL)
    bad["signals"] = [
        {"name": "momentum", "alias": "mom"},
        {"name": "rsi", "alias": "mom"},
    ]
    with pytest.raises(ValidationError, match="duplicate signal alias"):
        PipelineConfig(**bad)


def test_signal_may_depend_on_macro_alias() -> None:
    cfg_dict = dict(MINIMAL)
    cfg_dict["macro"] = {"series_ids": ["FEDFUNDS"], "source": "fred"}
    cfg_dict["signals"] = [
        {"name": "momentum", "alias": "mom"},
        {"name": "macro_overlay", "alias": "regime", "depends_on": ["macro_FEDFUNDS"]},
    ]
    cfg = PipelineConfig(**cfg_dict)
    assert cfg.macro.series_ids == ["FEDFUNDS"]


def test_load_config_from_yaml(tmp_path) -> None:
    yaml_text = textwrap.dedent(
        """
        name: from_yaml
        universe:
          symbols: [AAA, BBB]
          start: "2020-01-01"
          end: "2021-01-01"
          primary_source: yfinance
        signals:
          - name: momentum
            alias: mom
        strategy:
          name: rank_weighted_long_short
          signals: [mom]
        """
    )
    path = tmp_path / "config.yaml"
    path.write_text(yaml_text)
    cfg = load_config(path)
    assert cfg.name == "from_yaml"
    assert cfg.universe.symbols == ["AAA", "BBB"]


def test_load_config_missing_file_raises_config_error(tmp_path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "missing.yaml")


def test_load_config_invalid_yaml_raises_config_error(tmp_path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("name: [unterminated")
    with pytest.raises(ConfigError):
        load_config(path)
