"""Persistence helpers for job log events."""
from __future__ import annotations

from typing import Iterable

from sqlmodel import Session, select

from ..models import JobLogRecord
from ..schemas import JobLogCreate, JobLogModel


class JobLogStore:
    """Store and retrieve structured log events for manager jobs."""

    def __init__(self, engine) -> None:
        self._engine = engine

    def append(self, job_id: str, payload: JobLogCreate) -> JobLogModel:
        """Persist a new log event for the provided job identifier."""

        record = JobLogRecord(
            job_id=job_id,
            level=payload.level,
            message=payload.message,
            context=payload.context,
        )
        with Session(self._engine) as session:
            session.add(record)
            session.commit()
            session.refresh(record)
            return _to_model(record)

    def list_for_job(self, job_id: str, *, limit: int = 100) -> list[JobLogModel]:
        """Return log events associated with the given job."""

        statement = (
            select(JobLogRecord)
            .where(JobLogRecord.job_id == job_id)
            .order_by(JobLogRecord.created_at.asc(), JobLogRecord.id.asc())
            .limit(limit)
        )
        with Session(self._engine) as session:
            records: Iterable[JobLogRecord] = session.exec(statement)
            return [_to_model(record) for record in records]


def _to_model(record: JobLogRecord) -> JobLogModel:
    """Convert a database record into the API response model."""

    return JobLogModel(
        id=record.id,
        job_id=record.job_id,
        level=record.level,
        message=record.message,
        context=record.context,
        created_at=record.created_at,
    )

