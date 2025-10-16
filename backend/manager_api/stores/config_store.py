"""Database-backed configuration store for the Manager API."""
from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import Any

from sqlmodel import Session, select

from ..db import read_config
from ..models import ConfigRecord
from ..schemas import ConfigModel, ConfigUpdate


class ConfigStore:
    """Thread-safe interface over the persisted configuration."""

    def __init__(self, engine) -> None:
        self._engine = engine
        self._lock = Lock()

    def read(self) -> ConfigModel:
        """Return the current configuration model."""

        with Session(self._engine) as session:
            return read_config(session)

    def update(self, update: ConfigUpdate) -> ConfigModel:
        """Apply updates to the stored configuration."""

        update_payload = _extract_update(update)
        with self._lock, Session(self._engine) as session:
            record = session.exec(select(ConfigRecord).where(ConfigRecord.id == 1)).one_or_none()
            if record is None:
                raise RuntimeError("Configuration record missing from database")
            for key, value in update_payload.items():
                setattr(record, key, value)
            record.updated_at = datetime.utcnow()
            session.add(record)
            session.commit()
            session.refresh(record)
            return ConfigModel(
                resolver_url=record.resolver_url,
                strm_output_path=record.strm_output_path,
                tmdb_api_key=record.tmdb_api_key,
                html_title_fetch=record.html_title_fetch,
            )


def _extract_update(update: ConfigUpdate) -> dict[str, Any]:
    """Extract a payload suitable for model updates."""

    return update.model_dump(exclude_unset=True, exclude_none=True)
