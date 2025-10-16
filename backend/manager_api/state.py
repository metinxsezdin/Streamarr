"""Shared state container for the Manager API."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import Engine
from sqlmodel import Session

from .db import create_engine_from_settings, init_database
from .settings import ManagerSettings
from .stores.config_store import ConfigStore
from .stores.job_store import JobStore


@dataclass(slots=True)
class AppState:
    """Encapsulates mutable application state shared across routers."""

    settings: ManagerSettings
    config_store: ConfigStore
    job_store: JobStore
    engine: Engine

    def __init__(self, settings: ManagerSettings) -> None:
        self.settings = settings
        self.engine = create_engine_from_settings(settings)
        init_database(self.engine, settings)
        self.config_store = ConfigStore(self.engine)
        self.job_store = JobStore(self.engine)

    def session(self) -> Session:
        """Instantiate a SQLModel session for dependencies."""

        return Session(self.engine)
