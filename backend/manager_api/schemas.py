"""Pydantic models exposed by the Manager API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthStatus(BaseModel):
    """Service health payload."""

    status: Literal["ok"] = Field(default="ok")
    version: str = Field(default="0.1.0", description="Semantic version of the API service.")


class ConfigModel(BaseModel):
    """Represents the persisted manager configuration."""

    resolver_url: str = Field(..., description="Base URL for the resolver service.")
    strm_output_path: str = Field(..., description="Default STRM export path.")
    tmdb_api_key: str | None = Field(default=None, description="TMDB API key if configured.")
    html_title_fetch: bool = Field(
        default=True, description="Whether HTML title fallback is enabled when building catalogs."
    )


class ConfigUpdate(BaseModel):
    """Subset of configuration fields allowed to be updated at runtime."""

    resolver_url: str | None = Field(default=None)
    strm_output_path: str | None = Field(default=None)
    tmdb_api_key: str | None = Field(default=None)
    html_title_fetch: bool | None = Field(default=None)


class JobModel(BaseModel):
    """Represents a manager pipeline job."""

    id: str
    type: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: float = Field(ge=0, le=1)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None


class JobRunRequest(BaseModel):
    """Payload used to enqueue a new manager job."""

    type: str = Field(..., description="Job type identifier, e.g., collect or export.")
    payload: dict[str, Any] | None = Field(
        default=None, description="Optional JSON payload forwarded to the job runner."
    )


class StreamVariantModel(BaseModel):
    """Streaming variant metadata for library items."""

    source: str = Field(..., description="Source site providing the stream.")
    quality: str = Field(..., description="Human-readable stream quality (e.g., 1080p).")
    url: str = Field(..., description="Resolver URL to initiate playback.")


class LibraryItemModel(BaseModel):
    """Simplified library item definition exposed to the manager UI."""

    id: str
    title: str
    item_type: Literal["movie", "episode"]
    site: str
    year: int | None = None
    tmdb_id: str | None = None
    variants: list[StreamVariantModel] = Field(default_factory=list)


class LibraryListModel(BaseModel):
    """Paginated list container for library responses."""

    items: list[LibraryItemModel]
    total: int
    page: int
    page_size: int
