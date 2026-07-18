from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quant_research_api.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    configs: Mapped[list["SavedConfig"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    runs: Mapped[list["Run"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class SavedConfig(Base):
    __tablename__ = "saved_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped[User] = relationship(back_populates="configs")
    runs: Mapped[list["Run"]] = relationship(back_populates="config")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    config_id: Mapped[int | None] = mapped_column(ForeignKey("saved_configs.id"), nullable=True, index=True)

    # A snapshot of the exact config used, independent of later edits to the
    # SavedConfig row (or of an inline, never-saved config) -- run history
    # must stay reproducible even if the saved config is later changed/deleted.
    config_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)

    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # "research" | "backtest"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    report_dir: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped[User] = relationship(back_populates="runs")
    config: Mapped[SavedConfig | None] = relationship(back_populates="runs")
