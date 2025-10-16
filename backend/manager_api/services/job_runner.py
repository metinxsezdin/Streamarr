"""Helpers for synchronous job execution in the manager service."""
from __future__ import annotations

from typing import Any

from ..schemas import JobLogCreate, JobModel
from ..stores.job_log_store import JobLogStore
from ..stores.job_store import JobStore


def run_sync_job(
    job_store: JobStore,
    log_store: JobLogStore,
    job_type: str,
    payload: dict[str, Any] | None = None,
    *,
    worker_id: str = "manager-api",
) -> JobModel:
    """Enqueue a job and synchronously mark it as completed.

    The current Sprint 1 implementation executes jobs inline so the manager can
    surface predictable responses to API/CLI callers while the asynchronous
    queue is being designed. This helper captures the shared workflow so both
    the jobs router and other call sites (e.g., setup) can trigger the
    synchronous lifecycle consistently.
    """

    job = job_store.enqueue(job_type, payload)
    log_store.append(
        job.id,
        JobLogCreate(
            level="info",
            message=f"Job {job_type} enqueued",
            context={"payload": payload} if payload else None,
        ),
    )
    job = job_store.mark_running(job.id, worker_id=worker_id)
    log_store.append(job.id, JobLogCreate(level="info", message="Job started", context=None))
    job = job_store.mark_completed(job.id, progress=1.0)
    log_store.append(job.id, JobLogCreate(level="info", message="Job completed", context=None))
    return job
