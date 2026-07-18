from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from quant_research.config.schema import PipelineConfig
from quant_research.core.exceptions import ConfigError


def load_config(path: str | Path) -> PipelineConfig:
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text())
    except FileNotFoundError as exc:
        raise ConfigError(f"config file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"{path} must contain a YAML mapping at the top level")

    try:
        return PipelineConfig(**raw)
    except ValidationError as exc:
        raise ConfigError(f"invalid config in {path}:\n{exc}") from exc
