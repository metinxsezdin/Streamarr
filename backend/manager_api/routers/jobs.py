"""Job orchestration endpoints."""
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from ..dependencies import get_job_log_store, get_job_queue, get_job_store
from ..schemas import (
    JobCancelRequest,
    JobLogCreate,
    JobLogModel,
    JobMetricsModel,
    JobModel,
    JobRunRequest,
)
from ..services.queue import JobQueueError, JobQueueService
from ..stores.job_log_store import JobLogStore
from ..stores.job_store import JobStore

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/run", response_model=JobModel, status_code=201)
def run_job(
    request: JobRunRequest,
    store: JobStore = Depends(get_job_store),
    log_store: JobLogStore = Depends(get_job_log_store),
    queue: JobQueueService = Depends(get_job_queue),
) -> JobModel:
    """Enqueue a job for asynchronous execution via the Redis queue."""

    try:
        return queue.enqueue(store, log_store, request.type, request.payload)
    except JobQueueError as exc:  # pragma: no cover - queue failures
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("", response_model=list[JobModel])
def list_jobs(
    limit: int = Query(default=50, ge=1, le=100),
    statuses: Annotated[
        list[str] | None,
        Query(
            alias="status",
            description=(
                "Filter results to one or more job statuses. Repeat the query parameter "
                "to include multiple statuses."
            ),
        ),
    ] = None,
    job_type: str | None = Query(
        default=None,
        alias="type",
        description="Filter results to a specific job type.",
    ),
    store: JobStore = Depends(get_job_store),
) -> list[JobModel]:
    """Return the most recent jobs up to the requested limit."""

    return store.list(limit=limit, statuses=statuses, job_type=job_type)


@router.get("/metrics", response_model=JobMetricsModel)
def job_metrics(
    store: JobStore = Depends(get_job_store),
    queue: JobQueueService = Depends(get_job_queue),
) -> JobMetricsModel:
    """Return aggregate job telemetry combined with queue depth."""

    metrics = store.metrics()
    pending = len(queue.queue)
    return metrics.model_copy(update={"queue_depth": int(pending)})


@router.get("/{job_id}", response_model=JobModel)
def get_job(job_id: str, store: JobStore = Depends(get_job_store)) -> JobModel:
    """Return metadata for a single job, raising if missing."""

    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/cancel", response_model=JobModel)
def cancel_job(
    job_id: str,
    request: JobCancelRequest | None = Body(default=None),
    store: JobStore = Depends(get_job_store),
    log_store: JobLogStore = Depends(get_job_log_store),
) -> JobModel:
    """Cancel a queued or running job, recording an optional reason."""

    existing = store.get(job_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Job not found")

    reason = request.reason if request else None
    job = store.mark_cancelled(job_id, reason=reason)
    log_store.append(
        job_id,
        JobLogCreate(
            level="warning",
            message="Job cancelled",
            context={"reason": reason} if reason else None,
        ),
    )
    return job


@router.post("/{job_id}/logs", response_model=JobLogModel, status_code=201)
def append_job_log(
    job_id: str,
    payload: JobLogCreate,
    store: JobStore = Depends(get_job_store),
    log_store: JobLogStore = Depends(get_job_log_store),
) -> JobLogModel:
    """Create a new structured log event for an existing job."""

    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return log_store.append(job_id, payload)


@router.get("/{job_id}/logs", response_model=list[JobLogModel])
def list_job_logs(
    job_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    store: JobStore = Depends(get_job_store),
    log_store: JobLogStore = Depends(get_job_log_store),
) -> list[JobLogModel]:
    """Return log events associated with a job."""

    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return log_store.list_for_job(job_id, limit=limit)
