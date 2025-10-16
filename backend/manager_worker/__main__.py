"""Entry point for running the Streamarr manager RQ worker."""
from __future__ import annotations

import logging
import os

from rq import Worker, SimpleWorker

from backend.manager_api.settings import ManagerSettings
from backend.manager_api.services.queue import JobQueueService


def main() -> None:
    """Start an RQ worker connected to the configured manager queue."""

    settings = ManagerSettings()
    queue_service = JobQueueService(settings)
    
    # Use SimpleWorker on Windows to avoid fork issues
    worker_class = SimpleWorker if os.name == 'nt' else Worker
    worker = worker_class(
        [queue_service.queue],
        connection=queue_service.connection,
        name=settings.queue_worker_name,
    )

    logging.basicConfig(level=logging.INFO)
    worker.work(with_scheduler=False)


if __name__ == "__main__":  # pragma: no cover - manual entrypoint
    main()

