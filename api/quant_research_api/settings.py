from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QRA_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://qra:qra@localhost:5432/qra"
    redis_url: str = "redis://localhost:6379/0"

    # override via QRA_JWT_SECRET in any real deployment
    jwt_secret: str = "dev-secret-change-me-to-something-random-and-at-least-32-bytes-long"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24h

    cors_origins: list[str] = ["http://localhost:5173"]  # the Vite dev server

    # Where run artifacts (tearsheet markdown/PNGs) are written, per run id.
    artifacts_root: str = "api_data/reports"


settings = Settings()
