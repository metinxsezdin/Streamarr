"""Health endpoints."""
from fastapi import APIRouter, Depends

from ..dependencies import get_job_queue
from ..schemas import HealthStatus, QueueHealthStatus
from ..services.queue import JobQueueService

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
def get_health(queue: JobQueueService = Depends(get_job_queue)) -> HealthStatus:
    """Return service heartbeat information."""

    queue_status = QueueHealthStatus(status="ok")
    if not queue.ping():
        queue_status = QueueHealthStatus(status="error", detail="queue_unreachable")
    return HealthStatus(queue=queue_status)
