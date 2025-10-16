"""Database models for the Manager API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class ConfigRecord(SQLModel, table=True):
    """Persisted configuration row for manager defaults."""

    __tablename__ = "manager_config"

    id: int | None = Field(default=None, primary_key=True)
    resolver_url: str = Field(index=True)
    strm_output_path: str
    tmdb_api_key: str | None = Field(default=None)
    html_title_fetch: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class JobRecord(SQLModel, table=True):
    """Background job metadata persisted for orchestration."""

    __tablename__ = "manager_jobs"

    id: str = Field(primary_key=True, index=True)
    type: str = Field(index=True)
    status: str = Field(default="queued", index=True)
    progress: float = Field(default=0.0)
    payload: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    started_at: datetime | None = Field(default=None, index=True)
    finished_at: datetime | None = Field(default=None, index=True)
    error_message: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
