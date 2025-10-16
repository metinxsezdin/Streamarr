"""Smoke tests for the Manager API application factory."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.manager_api import create_app  # noqa: E402
from backend.manager_api.models import LibraryItemRecord  # noqa: E402
from backend.manager_api.schemas import ConfigModel, JobModel  # noqa: E402
from backend.manager_api.settings import ManagerSettings  # noqa: E402


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


def test_config_update_allows_clearing_tmdb_api_key(client: TestClient) -> None:
    """Setting the TMDB key to null should clear the persisted value."""

    seed_response = client.put("/config", json={"tmdb_api_key": "token"})
    assert seed_response.status_code == 200
    seeded = ConfigModel.model_validate(seed_response.json())
    assert seeded.tmdb_api_key == "token"

    clear_response = client.put("/config", json={"tmdb_api_key": None})
    assert clear_response.status_code == 200
    cleared = ConfigModel.model_validate(clear_response.json())
    assert cleared.tmdb_api_key is None

    persisted = ConfigModel.model_validate(client.get("/config").json())
    assert persisted.tmdb_api_key is None


def test_jobs_run_endpoint_creates_completed_job(client: TestClient) -> None:
    """POST /jobs/run should enqueue and complete a job synchronously."""

    response = client.post("/jobs/run", json={"type": "collect"})

    assert response.status_code == 201
    job = JobModel.model_validate(response.json())
    assert job.status == "completed"
    assert job.progress == 1.0
    assert job.started_at is not None
    assert job.finished_at is not None

    list_response = client.get("/jobs", params={"limit": 5})
    assert list_response.status_code == 200
    jobs = [JobModel.model_validate(item) for item in list_response.json()]
    assert any(item.id == job.id for item in jobs)

    detail_response = client.get(f"/jobs/{job.id}")
    assert detail_response.status_code == 200
    detail = JobModel.model_validate(detail_response.json())
    assert detail.id == job.id


def test_jobs_detail_returns_404_for_missing_job(client: TestClient) -> None:
    """GET /jobs/{id} should return 404 when job does not exist."""

    response = client.get("/jobs/missing")

    assert response.status_code == 404


def test_library_list_and_detail_round_trip(client: TestClient) -> None:
    """Library endpoints should expose paginated catalog metadata."""

    app_state = client.app.state.app_state
    with Session(app_state.engine) as session:
        session.add(
            LibraryItemRecord(
                id="movie-1",
                title="Example Movie",
                item_type="movie",
                site="dizibox",
                year=2024,
                tmdb_id="tmdb-100",
                variants=[
                    {
                        "source": "dizibox",
                        "quality": "1080p",
                        "url": "http://resolver/stream/movie-1",
                    }
                ],
                created_at=datetime(2025, 1, 1),
                updated_at=datetime(2025, 1, 1, 12, 0, 0),
            )
        )
        session.add(
            LibraryItemRecord(
                id="episode-1",
                title="Pilot Episode",
                item_type="episode",
                site="dizipal",
                variants=[
                    {
                        "source": "dizipal",
                        "quality": "720p",
                        "url": "http://resolver/stream/episode-1",
                    }
                ],
                created_at=datetime(2025, 1, 2),
                updated_at=datetime(2025, 1, 2, 8, 30, 0),
            )
        )
        session.commit()

    list_response = client.get("/library", params={"page": 1, "page_size": 1})
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] == 2
    assert payload["page"] == 1
    assert payload["page_size"] == 1
    assert len(payload["items"]) == 1

    query_response = client.get(
        "/library", params={"query": "pilot", "page": 1, "page_size": 10}
    )
    assert query_response.status_code == 200
    query_payload = query_response.json()
    assert query_payload["total"] == 1
    assert query_payload["items"][0]["id"] == "episode-1"

    detail_response = client.get("/library/movie-1")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["title"] == "Example Movie"
    assert detail["variants"][0]["quality"] == "1080p"


def test_library_detail_returns_404_for_missing_item(client: TestClient) -> None:
    """GET /library/{id} should surface a 404 when the item is absent."""

    response = client.get("/library/missing")

    assert response.status_code == 404
