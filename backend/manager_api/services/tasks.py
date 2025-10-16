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
        elif job_type == "strm_regenerate":
            _execute_strm_regenerate_job(job_id, log_store, resolved_settings, payload)
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


def _execute_strm_regenerate_job(job_id: str, log_store: JobLogStore, settings: ManagerSettings, payload: dict | None) -> None:
    """Execute STRM regenerate job: create .strm file for a library item."""
    
    if not payload or "library_item_id" not in payload:
        log_store.append(
            job_id,
            JobLogCreate(
                level="error",
                message="Missing library_item_id in payload",
                context={"payload": payload},
            ),
        )
        return
    
    library_item_id = payload["library_item_id"]
    log_store.append(
        job_id,
        JobLogCreate(
            level="info",
            message=f"Regenerating STRM for library item: {library_item_id}",
            context={"library_item_id": library_item_id},
        ),
    )
    
    # Get library item
    engine = create_engine_from_settings(settings)
    library_store = LibraryStore(engine)
    library_item = library_store.get(library_item_id)
    
    if not library_item:
        log_store.append(
            job_id,
            JobLogCreate(
                level="error",
                message=f"Library item not found: {library_item_id}",
                context={"library_item_id": library_item_id},
            ),
        )
        return
    
    # Create STRM file
    from pathlib import Path
    from ..utils.paths import ensure_strm_directory
    
    strm_filename = f"{library_item.title}.strm"
    strm_dir = ensure_strm_directory(settings.default_strm_output_path)
    strm_path = Path(strm_dir) / strm_filename
    
    # Write STRM file with the URL
    with open(strm_path, "w", encoding="utf-8") as f:
        f.write(library_item.url)
    
    log_store.append(
        job_id,
        JobLogCreate(
            level="info",
            message=f"STRM file created: {strm_path}",
            context={"strm_path": str(strm_path), "url": library_item.url},
        ),
    )


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
                
                # Create library item with variants from sources
                metadata = item.copy()
                if "sources" in metadata:
                    # Convert sources to variants format
                    variants = []
                    for source in metadata["sources"]:
                        variant = {
                            "source": source.get("site", "unknown"),
                            "quality": source.get("quality", "unknown"),
                            "url": source.get("url", "")
                        }
                        variants.append(variant)
                    metadata["sources"] = variants
                
                library_item = library_store.create(
                    title=title,
                    site=site,
                    url=url,
                    external_id=item_id,
                    metadata=metadata
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

