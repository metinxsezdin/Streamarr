"""FastAPI dependencies for the Manager API."""
from fastapi import Depends, Request
from sqlmodel import Session

from .state import AppState
from .stores.config_store import ConfigStore


def get_app_state(request: Request) -> AppState:
    """Resolve the shared application state from the FastAPI request."""
    return request.app.state.app_state


def get_config_store(app_state: AppState = Depends(get_app_state)) -> ConfigStore:
    """Return the configuration store dependency."""
    return app_state.config_store


def get_session(app_state: AppState = Depends(get_app_state)):
    """Provide a SQLModel session for request handlers."""

    session: Session = app_state.session()
    try:
        yield session
    finally:
        session.close()
