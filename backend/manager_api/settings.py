"""Runtime configuration for the Manager API."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ManagerSettings(BaseSettings):
    """Environment-aware settings for the Manager API service."""

    default_resolver_url: str = Field(
        "http://localhost:5055", description="Base URL for the existing resolver service."
    )
    default_strm_output_path: str = Field(
        "./data/strm", description="Filesystem path where STRM exports are written by default."
    )
    default_tmdb_api_key: str | None = Field(
        default=None, description="Optional TMDB API key used for metadata enrichment."
    )
    default_html_title_fetch: bool = Field(
        default=True, description="Whether HTML title fallback is enabled by default."
    )
    database_url: str = Field(
        default="sqlite:///./data/manager.db",
        description="Connection URL for the manager SQLite database.",
    )
    database_echo: bool = Field(
        default=False, description="Enable SQL echo for debugging queries."
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Connection URL for the Redis-backed job queue.",
    )
    redis_queue_name: str = Field(
        default="streamarr-manager",
        description="RQ queue name used for manager jobs.",
    )
    queue_worker_name: str = Field(
        default="manager-worker",
        description="Identifier used when reporting job worker executions.",
    )

    model_config = SettingsConfigDict(
        env_prefix="STREAMARR_MANAGER_",
        env_file=".env",
        env_file_encoding="utf-8",
    )
