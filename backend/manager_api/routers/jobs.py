"""Job orchestration endpoints."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import get_job_store
from ..schemas import JobModel, JobRunRequest
from ..stores.job_store import JobStore

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/run", response_model=JobModel, status_code=201)
def run_job(request: JobRunRequest, store: JobStore = Depends(get_job_store)) -> JobModel:
    """Enqueue a job and synchronously mark it as completed."""

    job = store.enqueue(request.type, request.payload)
    job = store.mark_running(job.id)
    return store.mark_completed(job.id, progress=1.0)


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


@router.get("/{job_id}", response_model=JobModel)
def get_job(job_id: str, store: JobStore = Depends(get_job_store)) -> JobModel:
    """Return metadata for a single job, raising if missing."""

    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
