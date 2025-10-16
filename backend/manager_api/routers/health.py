"""Health endpoints."""
from fastapi import APIRouter

from ..schemas import HealthStatus

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
def get_health() -> HealthStatus:
    """Return service heartbeat information."""
    return HealthStatus()
