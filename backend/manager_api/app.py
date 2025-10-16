"""Application factory for the Streamarr Manager API."""
from fastapi import FastAPI

from .routers import config, health, jobs, library, resolver, setup
from .settings import ManagerSettings
from .state import AppState


def create_app(settings: ManagerSettings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""

    resolved_settings = settings or ManagerSettings()
    app_state = AppState(settings=resolved_settings)

    app = FastAPI(title="Streamarr Manager API", version="0.1.0")
    app.state.app_state = app_state
    app.state.settings = app_state.settings

    for router in (
        setup.router,
        health.router,
        config.router,
        jobs.router,
        library.router,
        resolver.router,
    ):
        app.include_router(router)

    return app
