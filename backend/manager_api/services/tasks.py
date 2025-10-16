"""RQ task entrypoints executed by background workers."""
from __future__ import annotations

from typing import Any

import httpx
from rq import get_current_job

from ..db import create_engine_from_settings
from ..schemas import JobLogCreate
from ..settings import ManagerSettings
from ..stores.job_log_store import JobLogStore
from ..stores.job_store import JobStore
from ..stores.library_store import LibraryStore
from ..stores.config_store import ConfigStore


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
        
        # Execute specific job type
        if job_type == "bootstrap":
            _execute_bootstrap_job(job_id, log_store, resolved_settings)
        else:
            log_store.append(
                job_id,
                JobLogCreate(
                    level="warning",
                    message=f"Unknown job type: {job_type}",
                    context=None,
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


def _execute_bootstrap_job(job_id: str, log_store: JobLogStore, settings: ManagerSettings) -> None:
    """Execute bootstrap job: fetch catalog from resolver and populate library."""
    
    log_store.append(job_id, JobLogCreate(level="info", message="Starting bootstrap: fetching catalog", context=None))
    
    # Get config to find resolver URL
    engine = create_engine_from_settings(settings)
    config_store = ConfigStore(engine)
    config = config_store.read()
    
    try:
        # Fetch catalog from resolver
        with httpx.Client(timeout=30.0) as client:
            response = client.get(f"{config.resolver_url}/catalog")
            response.raise_for_status()
            catalog_data = response.json()
        
        log_store.append(
            job_id, 
            JobLogCreate(
                level="info", 
                message=f"Fetched catalog with {len(catalog_data)} items", 
                context={"item_count": len(catalog_data)}
            )
        )
        
        # Populate library store
        library_store = LibraryStore(engine)
        added_count = 0
        
        for item in catalog_data:
            try:
                # Extract basic info from catalog item
                title = item.get("title", "Unknown Title")
                site = item.get("site", "unknown")
                url = item.get("url", "")
                item_id = item.get("id", "")
                
                # Create library item
                library_item = library_store.create(
                    title=title,
                    site=site,
                    url=url,
                    external_id=item_id,
                    metadata=item
                )
                
                if library_item:
                    added_count += 1
                    
            except Exception as exc:
                log_store.append(
                    job_id,
                    JobLogCreate(
                        level="warning",
                        message=f"Failed to add item: {title}",
                        context={"error": str(exc), "item": item}
                    )
                )
        
        log_store.append(
            job_id,
            JobLogCreate(
                level="info",
                message=f"Bootstrap completed: added {added_count} items to library",
                context={"added_count": added_count, "total_catalog": len(catalog_data)}
            )
        )
        
    except httpx.HTTPError as exc:
        log_store.append(
            job_id,
            JobLogCreate(
                level="error",
                message=f"Failed to fetch catalog from resolver: {exc}",
                context={"resolver_url": config.resolver_url}
            )
        )
        raise
    except Exception as exc:
        log_store.append(
            job_id,
            JobLogCreate(
                level="error",
                message=f"Bootstrap failed: {exc}",
                context={"error": str(exc)}
            )
        )
        raise
    finally:
        engine.dispose()

