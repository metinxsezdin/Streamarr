"""RQ task entrypoints executed by background workers."""
from __future__ import annotations

from typing import Any

from rq import get_current_job

from ..db import create_engine_from_settings
from ..schemas import JobLogCreate
from ..settings import ManagerSettings
from ..stores.job_log_store import JobLogStore
from ..stores.job_store import JobStore


def execute_manager_job(
    *,
    job_id: str,
    job_type: str,
    payload: dict[str, Any] | None,
    settings: dict[str, Any],
    worker_name: str,
) -> None:
    """Background worker entrypoint for manager jobs."""

    resolved_settings = ManagerSettings.model_validate(settings)
    engine = create_engine_from_settings(resolved_settings)
    job_store = JobStore(engine)
    log_store = JobLogStore(engine)

    current_job = get_current_job()  # pragma: no branch - helper for diagnostics
    worker_id = worker_name
    if current_job and getattr(current_job, "worker_name", None):  # pragma: no cover - runtime path
        worker_id = current_job.worker_name  # type: ignore[assignment]

    job_store.mark_running(job_id, worker_id=worker_id)
    log_store.append(job_id, JobLogCreate(level="info", message="Job started", context=None))

    try:
        log_store.append(
            job_id,
            JobLogCreate(
                level="info",
                message=f"Executing {job_type} job",
                context={"payload": payload} if payload else None,
            ),
        )
        job_store.mark_completed(job_id, progress=1.0)
        log_store.append(job_id, JobLogCreate(level="info", message="Job completed", context=None))
    except Exception as exc:  # pragma: no cover - defensive branch
        job_store.mark_failed(job_id, error_message=str(exc), progress=0.0)
        log_store.append(
            job_id,
            JobLogCreate(
                level="error",
                message="Job failed",
                context={"error": str(exc)},
            ),
        )
        raise
    finally:
        engine.dispose()

