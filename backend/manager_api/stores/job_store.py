"""Database-backed job store for background task metadata."""
from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy import func
from sqlmodel import Session, select

from ..models import JobRecord
from ..schemas import JobMetricsModel, JobModel


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

    def mark_running(
        self,
        job_id: str,
        *,
        progress: float | None = None,
        worker_id: str | None = None,
    ) -> JobModel:
        """Transition a job into the running state."""

        return self._update_job(
            job_id,
            status="running",
            progress=0.0 if progress is None else progress,
            started_at=datetime.utcnow(),
            worker_id=worker_id,
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
        worker_id: str | None = None,
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
            if worker_id is not None:
                record.worker_id = worker_id
            record.updated_at = datetime.utcnow()

            session.add(record)
            session.commit()
            session.refresh(record)
            return _to_model(record)

    def metrics(self) -> JobMetricsModel:
        """Compute aggregate statistics for persisted jobs."""

        with Session(self._engine) as session:
            total = session.exec(
                select(func.count()).select_from(JobRecord)
            ).one()

            status_rows = session.exec(
                select(JobRecord.status, func.count())
                .group_by(JobRecord.status)
                .order_by(JobRecord.status)
            ).all()
            status_counts = {status: count for status, count in status_rows}

            type_rows = session.exec(
                select(JobRecord.type, func.count())
                .group_by(JobRecord.type)
                .order_by(JobRecord.type)
            ).all()
            type_counts = {job_type: count for job_type, count in type_rows}

            duration_rows = session.exec(
                select(JobRecord.started_at, JobRecord.finished_at)
                .where(JobRecord.started_at.is_not(None))
                .where(JobRecord.finished_at.is_not(None))
            ).all()
            durations = [
                (finished - started).total_seconds()
                for started, finished in duration_rows
                if started and finished
            ]
            average_duration = (
                sum(durations) / len(durations) if durations else None
            )

            last_finished = session.exec(
                select(JobRecord.finished_at)
                .where(JobRecord.finished_at.is_not(None))
                .order_by(JobRecord.finished_at.desc())
                .limit(1)
            ).one_or_none()

        return JobMetricsModel(
            total=total,
            status_counts=status_counts,
            type_counts=type_counts,
            average_duration_seconds=average_duration,
            last_finished_at=last_finished,
        )


def _to_model(record: JobRecord) -> JobModel:
    """Convert a JobRecord into the public response model."""

    duration_seconds: float | None = None
    if record.started_at and record.finished_at:
        duration_seconds = (
            record.finished_at - record.started_at
        ).total_seconds()

    return JobModel(
        id=record.id,
        type=record.type,
        status=record.status,
        progress=record.progress,
        worker_id=record.worker_id,
        payload=record.payload,
        created_at=record.created_at,
        updated_at=record.updated_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
        error_message=record.error_message,
        duration_seconds=duration_seconds,
    )
