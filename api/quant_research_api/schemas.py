from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from quant_research.config.schema import PipelineConfig
from quant_research.core.exceptions import QuantResearchError


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _validate_pipeline_config(value: dict[str, Any]) -> dict[str, Any]:
    """Reuses the engine's own PipelineConfig validation so a malformed config
    is rejected at save/run time with the same errors `quant-research
    validate-config` would give, not discovered later inside a Celery worker."""
    try:
        PipelineConfig(**value)
    except (ValueError, TypeError, QuantResearchError) as exc:
        raise ValueError(f"invalid pipeline config: {exc}") from exc
    return value


class SavedConfigCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    config_json: dict[str, Any]

    @field_validator("config_json")
    @classmethod
    def _check_config(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_pipeline_config(value)


class SavedConfigUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    config_json: dict[str, Any] | None = None

    @field_validator("config_json")
    @classmethod
    def _check_config(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return None if value is None else _validate_pipeline_config(value)


class SavedConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    config_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class RunCreate(BaseModel):
    kind: Literal["research", "backtest"] = "backtest"
    config_id: int | None = None
    config_json: dict[str, Any] | None = None

    @field_validator("config_json")
    @classmethod
    def _check_config(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return None if value is None else _validate_pipeline_config(value)


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    status: str
    config_id: int | None
    error_message: str | None
    result_json: dict[str, Any] | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class RegistryOut(BaseModel):
    data_sources: list[str]
    macro_sources: list[str]
    fundamentals_sources: list[str]
    cache_backends: list[str]
    universe_providers: list[str]
    signals: list[str]
    strategies: list[str]
