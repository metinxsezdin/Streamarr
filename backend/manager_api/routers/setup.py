"""Initial setup endpoint for the manager service."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..dependencies import get_config_store, get_job_log_store, get_job_store
from ..schemas import ConfigModel, JobModel, SetupRequest, SetupResponse
from ..services.job_runner import run_sync_job
from ..stores.config_store import ConfigStore
from ..stores.job_log_store import JobLogStore
from ..stores.job_store import JobStore

router = APIRouter(tags=["setup"])


@router.post("/setup", response_model=SetupResponse)
def perform_setup(
    request: SetupRequest,
    config_store: ConfigStore = Depends(get_config_store),
    job_store: JobStore = Depends(get_job_store),
    log_store: JobLogStore = Depends(get_job_log_store),
) -> SetupResponse:
    """Persist the initial configuration and optionally trigger a bootstrap job."""

    config = config_store.replace(
        ConfigModel(
            resolver_url=request.resolver_url,
            strm_output_path=request.strm_output_path,
            tmdb_api_key=request.tmdb_api_key,
            html_title_fetch=request.html_title_fetch,
        )
    )

    job: JobModel | None = None
    if request.run_initial_job:
        job = run_sync_job(
            job_store,
            log_store,
            request.initial_job_type,
            request.initial_job_payload,
        )

    return SetupResponse(config=config, job=job)
