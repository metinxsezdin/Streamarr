"""Entry point for running the Streamarr manager RQ worker."""
from __future__ import annotations

import logging

from rq import Worker

from backend.manager_api.settings import ManagerSettings
from backend.manager_api.services.queue import JobQueueService


def main() -> None:
    """Start an RQ worker connected to the configured manager queue."""

    settings = ManagerSettings()
    queue_service = JobQueueService(settings)
    worker = Worker(
        [queue_service.queue],
        connection=queue_service.connection,
        name=settings.queue_worker_name,
    )

    logging.basicConfig(level=logging.INFO)
    worker.work(with_scheduler=True)


if __name__ == "__main__":  # pragma: no cover - manual entrypoint
    main()

