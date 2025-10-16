"""Pydantic models exposed by the Manager API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class QueueHealthStatus(BaseModel):
    """Represents Redis queue connectivity status."""

    status: Literal["ok", "error"] = Field(default="ok")
    detail: str | None = Field(
        default=None, description="Optional diagnostic message when the queue is unavailable."
    )


class HealthStatus(BaseModel):
    """Service health payload."""

    status: Literal["ok"] = Field(default="ok")
    version: str = Field(default="0.1.0", description="Semantic version of the API service.")
    queue: QueueHealthStatus = Field(
        default_factory=QueueHealthStatus,
        description="Health information for the background job queue.",
    )


class ResolverProcessStatusModel(BaseModel):
    """Represents the resolver process lifecycle state exposed by the API."""

    running: bool = Field(description="Whether the manager currently has a resolver process running.")
    pid: int | None = Field(
        default=None, description="Process identifier when the resolver is running."
    )
    exit_code: int | None = Field(
        default=None,
        description="Exit code from the last managed resolver process if it has stopped.",
    )


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


class SetupRequest(ConfigModel):
    """Payload accepted by the initial setup endpoint."""

    run_initial_job: bool = Field(
        default=False,
        description="Whether to trigger a bootstrap job after persisting configuration.",
    )
    initial_job_type: str = Field(
        default="bootstrap",
        description="Job type enqueued when run_initial_job is enabled.",
    )
    initial_job_payload: dict[str, Any] | None = Field(
        default=None,
        description="Optional payload forwarded to the bootstrap job.",
    )


class SetupResponse(BaseModel):
    """Response returned after performing initial setup."""

    config: ConfigModel = Field(description="Persisted configuration state after setup.")
    job: JobModel | None = Field(
        default=None,
        description="Job triggered as part of setup when run_initial_job is enabled.",
    )


class JobModel(BaseModel):
    """Represents a manager pipeline job."""

    id: str
    type: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    progress: float = Field(ge=0, le=1)
    worker_id: str | None = Field(
        default=None, description="Identifier for the worker processing the job."
    )
    payload: dict[str, Any] | None = Field(
        default=None, description="Optional JSON payload forwarded to the runner."
    )
    created_at: datetime = Field(
        description="Timestamp when the job record was created."
    )
    updated_at: datetime = Field(
        description="Timestamp when the job record was last updated."
    )
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    duration_seconds: float | None = Field(
        default=None,
        description="Execution duration calculated from started and finished timestamps.",
    )


class JobMetricsModel(BaseModel):
    """Aggregate statistics for background job processing."""

    total: int = Field(description="Total number of job records persisted in the store.")
    status_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Count of jobs grouped by current status.",
    )
    type_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Count of jobs grouped by job type identifier.",
    )
    average_duration_seconds: float | None = Field(
        default=None,
        description="Average duration in seconds for completed jobs when both start and finish timestamps are recorded.",
    )
    last_finished_at: datetime | None = Field(
        default=None,
        description="Timestamp of the most recently finished job regardless of outcome.",
    )
    queue_depth: int = Field(
        default=0,
        description="Number of jobs currently waiting in the Redis queue.",
    )


class JobLogCreate(BaseModel):
    """Payload used to append a new job log entry."""

    level: Literal["debug", "info", "warning", "error"] = Field(
        default="info", description="Severity level of the log entry."
    )
    message: str = Field(..., description="Human-readable log message.")
    context: dict[str, Any] | None = Field(
        default=None,
        description="Optional structured context payload for the log entry.",
    )


class JobLogModel(JobLogCreate):
    """Represents a persisted job log entry."""

    id: int
    job_id: str
    created_at: datetime


class JobRunRequest(BaseModel):
    """Payload used to enqueue a new manager job."""

    type: str = Field(..., description="Job type identifier, e.g., collect or export.")
    payload: dict[str, Any] | None = Field(
        default=None, description="Optional JSON payload forwarded to the job runner."
    )


class JobCancelRequest(BaseModel):
    """Payload used when cancelling a job."""

    reason: str | None = Field(
        default=None, description="Optional reason recorded with the cancellation."
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


LibrarySortOption = Literal[
    "updated_desc",
    "updated_asc",
    "title_asc",
    "title_desc",
    "year_desc",
    "year_asc",
]


class LibraryMetricsModel(BaseModel):
    """Aggregate statistics for library catalog insights."""

    total: int = Field(description="Total number of items in the catalog.")
    site_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Breakdown of items per source site.",
    )
    type_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Breakdown of items per item type.",
    )
    tmdb_enriched: int = Field(
        description="Number of items linked to TMDB metadata.",
    )
    tmdb_missing: int = Field(
        description="Number of items missing TMDB enrichment.",
    )
