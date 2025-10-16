"""FastAPI dependencies for the Manager API."""
from fastapi import Depends, Request
from sqlmodel import Session

from .services import JobQueueService, ResolverService
from .state import AppState
from .settings import ManagerSettings
from .stores.config_store import ConfigStore
from .stores.job_log_store import JobLogStore
from .stores.job_store import JobStore
from .stores.library_store import LibraryStore


def get_app_state(request: Request) -> AppState:
    """Resolve the shared application state from the FastAPI request."""
    return request.app.state.app_state


def get_config_store(app_state: AppState = Depends(get_app_state)) -> ConfigStore:
    """Return the configuration store dependency."""
    return app_state.config_store


def get_job_store(app_state: AppState = Depends(get_app_state)) -> JobStore:
    """Return the job store dependency."""
    return app_state.job_store


def get_job_log_store(app_state: AppState = Depends(get_app_state)) -> JobLogStore:
    """Return the job log store dependency."""

    return app_state.job_log_store


def get_library_store(app_state: AppState = Depends(get_app_state)) -> LibraryStore:
    """Return the library store dependency."""

    return app_state.library_store


def get_resolver_service(app_state: AppState = Depends(get_app_state)) -> ResolverService:
    """Expose the resolver service helper for request handlers."""

    return app_state.resolver_service


def get_job_queue(app_state: AppState = Depends(get_app_state)) -> JobQueueService:
    """Return the job queue integration service."""

    return app_state.job_queue


def get_settings(app_state: AppState = Depends(get_app_state)) -> ManagerSettings:
    """Expose the application settings dependency."""

    return app_state.settings


def get_session(app_state: AppState = Depends(get_app_state)):
    """Provide a SQLModel session for request handlers."""

    session: Session = app_state.session()
    try:
        yield session
    finally:
        session.close()
