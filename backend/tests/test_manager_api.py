"""Smoke tests for the Manager API application factory."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.manager_api import create_app
from backend.manager_api.schemas import ConfigModel
from backend.manager_api.settings import ManagerSettings


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    """Provide a test client backed by an isolated SQLite database."""

    db_path = tmp_path / "manager.db"
    settings = ManagerSettings(database_url=f"sqlite:///{db_path}")
    app = create_app(settings=settings)
    return TestClient(app)


def test_health_endpoint_reports_ok_status(client: TestClient) -> None:
    """The /health endpoint should respond with an OK status payload."""

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_config_round_trip_updates_database_store(client: TestClient) -> None:
    """PUT /config should persist updates to the database-backed store."""

    new_payload = {
        "resolver_url": "http://resolver.internal:5055",
        "strm_output_path": "/mnt/strm",
        "html_title_fetch": False,
    }

    put_response = client.put("/config", json=new_payload)
    assert put_response.status_code == 200

    updated = ConfigModel.model_validate(put_response.json())
    for key, value in new_payload.items():
        assert getattr(updated, key) == value

    get_response = client.get("/config")
    assert get_response.status_code == 200
    persisted = ConfigModel.model_validate(get_response.json())
    for key, value in new_payload.items():
        assert getattr(persisted, key) == value
