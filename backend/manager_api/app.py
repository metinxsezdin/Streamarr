"""Application factory for the Streamarr Manager API."""
from fastapi import FastAPI

from .routers import config, health, jobs
from .settings import ManagerSettings
from .state import AppState


def create_app(settings: ManagerSettings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    resolved_settings = settings or ManagerSettings()
    app = FastAPI(title="Streamarr Manager API", version="0.1.0")

    app_state = AppState(settings=resolved_settings)
    app.state.settings = resolved_settings
    app.state.app_state = app_state

    app.include_router(health.router)
    app.include_router(config.router)
    app.include_router(jobs.router)

    return app
