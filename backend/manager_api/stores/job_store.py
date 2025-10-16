"""Database-backed job store for background task metadata."""
from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import Any, Iterable
from uuid import uuid4

from sqlmodel import Session, select

from ..models import JobRecord
from ..schemas import JobModel


class JobStore:
    """Thread-safe CRUD interface for manager jobs."""

    def __init__(self, engine) -> None:
        self._engine = engine
        self._lock = Lock()

    def enqueue(self, job_type: str, payload: dict[str, Any] | None = None) -> JobModel:
        """Create a queued job entry and return its model representation."""

        record = JobRecord(
            id=uuid4().hex,
            type=job_type,
            status="queued",
            progress=0.0,
            payload=payload,
        )
        with self._lock, Session(self._engine) as session:
            session.add(record)
            session.commit()
            session.refresh(record)
            return _to_model(record)

    def list(
        self,
        *,
        limit: int = 50,
        statuses: list[str] | None = None,
        job_type: str | None = None,
    ) -> list[JobModel]:
        """Return the most recent jobs up to the requested limit with optional filters."""

        statement = select(JobRecord)

        if statuses:
            normalized_statuses = sorted({status.lower() for status in statuses if status})
            if normalized_statuses:
                statement = statement.where(JobRecord.status.in_(normalized_statuses))

        if job_type:
            statement = statement.where(JobRecord.type == job_type)

        statement = statement.order_by(JobRecord.created_at.desc()).limit(limit)
        with Session(self._engine) as session:
            records: Iterable[JobRecord] = session.exec(statement)
            return [_to_model(record) for record in records]

    def get(self, job_id: str) -> JobModel | None:
        """Fetch a single job by identifier."""

        with Session(self._engine) as session:
            record = session.get(JobRecord, job_id)
            return _to_model(record) if record else None

    def mark_running(self, job_id: str, *, progress: float | None = None) -> JobModel:
        """Transition a job into the running state."""

        return self._update_job(
            job_id,
            status="running",
            progress=0.0 if progress is None else progress,
            started_at=datetime.utcnow(),
        )

    def mark_completed(self, job_id: str, *, progress: float = 1.0) -> JobModel:
        """Transition a job into the completed state."""

        return self._update_job(
            job_id,
            status="completed",
            progress=progress,
            finished_at=datetime.utcnow(),
        )

    def mark_failed(self, job_id: str, *, error_message: str, progress: float | None = None) -> JobModel:
        """Transition a job into the failed state."""

        return self._update_job(
            job_id,
            status="failed",
            progress=progress,
            finished_at=datetime.utcnow(),
            error_message=error_message,
        )

    def mark_cancelled(
        self,
        job_id: str,
        *,
        reason: str | None = None,
        progress: float | None = None,
    ) -> JobModel:
        """Transition a job into the cancelled state."""

        return self._update_job(
            job_id,
            status="cancelled",
            progress=progress,
            finished_at=datetime.utcnow(),
            error_message=reason,
        )

    def _update_job(
        self,
        job_id: str,
        *,
        status: str,
        progress: float | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        error_message: str | None = None,
    ) -> JobModel:
        with self._lock, Session(self._engine) as session:
            record = session.get(JobRecord, job_id)
            if record is None:
                raise RuntimeError(f"Job {job_id} not found")

            record.status = status
            if progress is not None:
                record.progress = progress
            if started_at is not None and record.started_at is None:
                record.started_at = started_at
            if finished_at is not None:
                record.finished_at = finished_at
            if error_message is not None:
                record.error_message = error_message
            record.updated_at = datetime.utcnow()

            session.add(record)
            session.commit()
            session.refresh(record)
            return _to_model(record)


def _to_model(record: JobRecord) -> JobModel:
    """Convert a JobRecord into the public response model."""

    return JobModel(
        id=record.id,
        type=record.type,
        status=record.status,
        progress=record.progress,
        payload=record.payload,
        created_at=record.created_at,
        updated_at=record.updated_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
        error_message=record.error_message,
    )
