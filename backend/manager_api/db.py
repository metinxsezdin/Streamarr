"""Database helpers for the Manager API."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from .models import ConfigRecord
from .schemas import ConfigModel
from .settings import ManagerSettings
from .utils.paths import ensure_strm_directory


def _ensure_sqlite_path(database_url: str) -> None:
    """Create parent directories when using a SQLite URL."""

    if database_url.startswith("sqlite:///"):
        path_part = database_url.removeprefix("sqlite:///").split("?")[0]
        if path_part:
            db_path = Path(path_part)
            db_path.parent.mkdir(parents=True, exist_ok=True)


def create_engine_from_settings(settings: ManagerSettings) -> Engine:
    """Create a SQLModel engine using manager settings."""

    _ensure_sqlite_path(settings.database_url)
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_engine(settings.database_url, echo=settings.database_echo, connect_args=connect_args)


def init_database(engine: Engine, settings: ManagerSettings) -> None:
    """Create tables and seed default configuration."""

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        record = session.get(ConfigRecord, 1)
        if record is None:
            default_strm_path = ensure_strm_directory(settings.default_strm_output_path)
            defaults = ConfigRecord(
                id=1,
                resolver_url=settings.default_resolver_url,
                strm_output_path=default_strm_path,
                tmdb_api_key=settings.default_tmdb_api_key,
                html_title_fetch=settings.default_html_title_fetch,
            )
            session.add(defaults)
            session.commit()


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """Yield a SQLModel session that closes automatically."""

    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:  # pragma: no cover - re-raise after rollback
        session.rollback()
        raise
    finally:
        session.close()


def read_config(session: Session) -> ConfigModel:
    """Fetch the persisted configuration as a Pydantic model."""

    record = session.get(ConfigRecord, 1)
    if record is None:
        raise RuntimeError("Configuration record missing from database")
    return ConfigModel(
        resolver_url=record.resolver_url,
        strm_output_path=record.strm_output_path,
        tmdb_api_key=record.tmdb_api_key,
        html_title_fetch=record.html_title_fetch,
    )
