"""Smoke tests for the Manager API application factory."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from rq.worker import SimpleWorker
from sqlmodel import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.manager_api import create_app  # noqa: E402
from backend.manager_api.models import LibraryItemRecord  # noqa: E402
from backend.manager_api.schemas import (  # noqa: E402
    ConfigModel,
    JobLogModel,
    JobModel,
)
from backend.manager_api.services import (  # noqa: E402
    ResolverAlreadyRunningError,
    ResolverNotRunningError,
    ResolverProcessStatus,
    ResolverServiceError,
)
from backend.manager_api.settings import ManagerSettings  # noqa: E402


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    """Provide a test client backed by an isolated SQLite database."""

    db_path = tmp_path / "manager.db"
    settings = ManagerSettings(
        database_url=f"sqlite:///{db_path}",
        redis_url="fakeredis://",
    )
    app = create_app(settings=settings)
    return TestClient(app)


def drain_jobs(client: TestClient) -> None:
    """Drain queued jobs using an in-process RQ worker."""

    app_state = client.app.state.app_state
    worker = SimpleWorker([app_state.job_queue.queue], connection=app_state.job_queue.connection)
    worker.work(burst=True)


def test_health_endpoint_reports_ok_status(client: TestClient) -> None:
    """The /health endpoint should respond with an OK status payload."""

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "0.1.0",
        "queue": {"status": "ok", "detail": None},
    }


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


def test_setup_endpoint_persists_configuration(client: TestClient) -> None:
    """POST /setup should overwrite the stored configuration."""

    payload = {
        "resolver_url": "http://resolver:5055",
        "strm_output_path": "/data/strm",
        "tmdb_api_key": "abc123",
        "html_title_fetch": False,
    }

    response = client.post("/setup", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["job"] is None
    config = ConfigModel.model_validate(body["config"])
    for key, value in payload.items():
        assert getattr(config, key) == value

    persisted = ConfigModel.model_validate(client.get("/config").json())
    for key, value in payload.items():
        assert getattr(persisted, key) == value


def test_setup_endpoint_can_trigger_bootstrap_job(client: TestClient) -> None:
    """Setup should optionally trigger a bootstrap job and return its payload."""

    response = client.post(
        "/setup",
        json={
            "resolver_url": "http://resolver:5055",
            "strm_output_path": "/data/strm",
            "html_title_fetch": True,
            "run_initial_job": True,
            "initial_job_type": "bootstrap",
            "initial_job_payload": {"collect": True},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["job"] is not None
    job = JobModel.model_validate(body["job"])
    assert job.type == "bootstrap"
    assert job.payload == {"collect": True}
    assert job.status == "queued"

    drain_jobs(client)
    final_response = client.get(f"/jobs/{job.id}")
    assert final_response.status_code == 200
    final_job = JobModel.model_validate(final_response.json())
    assert final_job.status == "completed"

def test_jobs_run_endpoint_tracks_job_completion(client: TestClient) -> None:
    """POST /jobs/run should enqueue a job and mark it completed after worker processing."""

    response = client.post(
        "/jobs/run",
        json={"type": "collect", "payload": {"full": True}},
    )

    assert response.status_code == 201
    job = JobModel.model_validate(response.json())
    assert job.status == "queued"
    assert job.progress == 0.0
    assert job.worker_id is None
    assert job.payload == {"full": True}
    assert job.created_at <= job.updated_at
    assert job.started_at is None
    assert job.finished_at is None
    assert job.duration_seconds is None

    drain_jobs(client)
    detail_response = client.get(f"/jobs/{job.id}")
    assert detail_response.status_code == 200
    completed = JobModel.model_validate(detail_response.json())
    assert completed.status == "completed"
    assert completed.progress == 1.0
    assert completed.worker_id is not None
    assert completed.worker_id != ""
    assert completed.payload == {"full": True}
    assert completed.created_at <= completed.updated_at
    assert completed.started_at is not None
    assert completed.finished_at is not None
    assert completed.duration_seconds is not None
    assert completed.duration_seconds >= 0

    list_response = client.get("/jobs", params={"limit": 5})
    assert list_response.status_code == 200
    jobs = [JobModel.model_validate(item) for item in list_response.json()]
    assert any(item.id == job.id for item in jobs)



def test_jobs_run_persists_log_entries(client: TestClient) -> None:
    """Running a job should create structured log entries."""

    response = client.post("/jobs/run", json={"type": "collect"})
    job = JobModel.model_validate(response.json())

    drain_jobs(client)
    logs_response = client.get(f"/jobs/{job.id}/logs")
    assert logs_response.status_code == 200
    payload = [JobLogModel.model_validate(item) for item in logs_response.json()]
    assert len(payload) == 4
    messages = [entry.message for entry in payload]
    assert messages == [
        "Job collect enqueued",
        "Job started",
        "Executing collect job",
        "Job completed",
    ]


def test_jobs_detail_returns_404_for_missing_job(client: TestClient) -> None:
    """GET /jobs/{id} should return 404 when job does not exist."""

    response = client.get("/jobs/missing")

    assert response.status_code == 404


def test_jobs_list_supports_status_and_type_filters(client: TestClient) -> None:
    """GET /jobs should honor optional status and type filters."""

    app_state = client.app.state.app_state
    job_store = app_state.job_store

    completed = job_store.enqueue("collect")
    job_store.mark_running(completed.id, worker_id="runner-1")
    job_store.mark_completed(completed.id)

    failed = job_store.enqueue("collect")
    job_store.mark_failed(failed.id, error_message="pipeline failed", progress=0.5)

    queued = job_store.enqueue("catalog")
    cancelled = job_store.enqueue("collect")
    job_store.mark_cancelled(cancelled.id, reason="user aborted")

    status_response = client.get(
        "/jobs",
        params=[
            ("status", "completed"),
            ("status", "failed"),
            ("status", "cancelled"),
            ("limit", "10"),
        ],
    )
    assert status_response.status_code == 200
    status_payload = [JobModel.model_validate(item) for item in status_response.json()]
    assert {job.status for job in status_payload} == {"completed", "failed", "cancelled"}
    assert any(job.worker_id == "runner-1" for job in status_payload)
    assert all(job.id != queued.id for job in status_payload)

    type_response = client.get("/jobs", params={"type": "collect", "limit": 10})
    assert type_response.status_code == 200
    type_payload = [JobModel.model_validate(item) for item in type_response.json()]
    assert {job.type for job in type_payload} == {"collect"}
    assert any(job.id == failed.id for job in type_payload)
    assert all(job.id != queued.id for job in type_payload)


def test_jobs_cancel_endpoint_marks_job_cancelled(client: TestClient) -> None:
    """POST /jobs/{id}/cancel should mark a job as cancelled."""

    app_state = client.app.state.app_state
    job_store = app_state.job_store

    job = job_store.enqueue("collect")

    response = client.post(
        f"/jobs/{job.id}/cancel",
        json={"reason": "user requested"},
    )

    assert response.status_code == 200
    payload = JobModel.model_validate(response.json())
    assert payload.status == "cancelled"
    assert payload.error_message == "user requested"
    assert payload.finished_at is not None
    assert payload.duration_seconds is None

    detail_response = client.get(f"/jobs/{job.id}")
    assert detail_response.status_code == 200
    detail = JobModel.model_validate(detail_response.json())
    assert detail.status == "cancelled"
    assert detail.error_message == "user requested"


def test_job_logs_endpoints_support_manual_append(client: TestClient) -> None:
    """POST /jobs/{id}/logs should append new entries retrievable via GET."""

    created = client.post("/jobs/run", json={"type": "collect"})
    job = JobModel.model_validate(created.json())

    append_response = client.post(
        f"/jobs/{job.id}/logs",
        json={
            "level": "error",
            "message": "Job failed to fetch resource",
            "context": {"status": 500},
        },
    )

    assert append_response.status_code == 201
    appended = JobLogModel.model_validate(append_response.json())
    assert appended.level == "error"
    assert appended.context == {"status": 500}

    logs_response = client.get(
        f"/jobs/{job.id}/logs", params={"limit": 5}
    )
    logs = [JobLogModel.model_validate(item) for item in logs_response.json()]
    assert any(entry.message == "Job failed to fetch resource" for entry in logs)


def test_job_logs_endpoints_handle_missing_job(client: TestClient) -> None:
    """Log append and fetch endpoints should return 404 for unknown jobs."""

    append_response = client.post(
        "/jobs/missing/logs",
        json={"message": "unknown", "level": "info"},
    )
    assert append_response.status_code == 404

    fetch_response = client.get("/jobs/missing/logs")
    assert fetch_response.status_code == 404


def test_jobs_cancel_returns_404_for_missing_job(client: TestClient) -> None:
    """POST /jobs/{id}/cancel should return 404 when the job is missing."""

    response = client.post("/jobs/missing/cancel")

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
                year=2019,
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

    site_response = client.get("/library", params={"site": "dizipal"})
    assert site_response.status_code == 200
    site_payload = site_response.json()
    assert site_payload["total"] == 1
    assert site_payload["items"][0]["id"] == "episode-1"

    multi_site_response = client.get(
        "/library",
        params=[("site", "dizibox"), ("site", "dizipal"), ("page_size", "10")],
    )
    assert multi_site_response.status_code == 200
    multi_site_payload = multi_site_response.json()
    assert multi_site_payload["total"] == 2
    assert [item["id"] for item in multi_site_payload["items"]] == [
        "episode-1",
        "movie-1",
    ]

    type_response = client.get("/library", params={"item_type": "movie"})
    assert type_response.status_code == 200
    type_payload = type_response.json()
    assert type_payload["total"] == 1
    assert type_payload["items"][0]["id"] == "movie-1"

    tmdb_response = client.get("/library", params={"has_tmdb": True})
    assert tmdb_response.status_code == 200
    tmdb_payload = tmdb_response.json()
    assert tmdb_payload["total"] == 1
    assert tmdb_payload["items"][0]["id"] == "movie-1"

    missing_tmdb_response = client.get("/library", params={"has_tmdb": False})
    assert missing_tmdb_response.status_code == 200
    missing_tmdb_payload = missing_tmdb_response.json()
    assert missing_tmdb_payload["total"] == 1
    assert missing_tmdb_payload["items"][0]["id"] == "episode-1"

    year_response = client.get("/library", params={"year": 2024})
    assert year_response.status_code == 200
    year_payload = year_response.json()
    assert year_payload["total"] == 1
    assert year_payload["items"][0]["id"] == "movie-1"

    year_min_response = client.get("/library", params={"year_min": 2020})
    assert year_min_response.status_code == 200
    year_min_payload = year_min_response.json()
    assert year_min_payload["total"] == 1
    assert year_min_payload["items"][0]["id"] == "movie-1"

    year_max_response = client.get("/library", params={"year_max": 2019})
    assert year_max_response.status_code == 200
    year_max_payload = year_max_response.json()
    assert year_max_payload["total"] == 1
    assert year_max_payload["items"][0]["id"] == "episode-1"

    sort_response = client.get(
        "/library",
        params={"sort": "title_desc", "page_size": 10},
    )
    assert sort_response.status_code == 200
    sort_payload = sort_response.json()
    assert [item["id"] for item in sort_payload["items"]] == [
        "episode-1",
        "movie-1",
    ]

    detail_response = client.get("/library/movie-1")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["title"] == "Example Movie"
    assert detail["variants"][0]["quality"] == "1080p"


def test_library_metrics_returns_aggregate_counts(client: TestClient) -> None:
    """/library/metrics should surface aggregate catalog statistics."""

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
            )
        )
        session.add(
            LibraryItemRecord(
                id="episode-1",
                title="Pilot Episode",
                item_type="episode",
                site="dizipal",
                year=2019,
            )
        )
        session.commit()

    response = client.get("/library/metrics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["tmdb_enriched"] == 1
    assert payload["tmdb_missing"] == 1
    assert payload["site_counts"] == {"dizibox": 1, "dizipal": 1}
    assert payload["type_counts"] == {"episode": 1, "movie": 1}


def test_library_detail_returns_404_for_missing_item(client: TestClient) -> None:
    """GET /library/{id} should surface a 404 when the item is absent."""

    response = client.get("/library/missing")

    assert response.status_code == 404


def test_resolver_health_proxies_resolver_payload(client: TestClient) -> None:
    """GET /resolver/health should return the proxied resolver response."""

    stub = StubResolverService(payload={"status": "ok", "cache_size": 3})
    client.app.state.app_state.resolver_service = stub

    response = client.get("/resolver/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "cache_size": 3}
    assert stub.calls == ["http://localhost:5055"]


def test_resolver_health_returns_502_on_failure(client: TestClient) -> None:
    """Resolver failures should be surfaced as a 502 response."""

    stub = StubResolverService(error=ResolverServiceError("resolver offline"))
    client.app.state.app_state.resolver_service = stub

    response = client.get("/resolver/health")

    assert response.status_code == 502
    assert response.json()["detail"] == "resolver offline"


def test_resolver_start_launches_process(client: TestClient) -> None:
    """POST /resolver/start should ask the service to launch the resolver."""

    stub = StubResolverService(
        start_status=ResolverProcessStatus(running=True, pid=987, exit_code=None)
    )
    client.app.state.app_state.resolver_service = stub

    response = client.post("/resolver/start")

    assert response.status_code == 200
    assert response.json() == {"running": True, "pid": 987, "exit_code": None}
    assert stub.start_calls == ["http://localhost:5055"]


def test_resolver_start_conflict_returns_409(client: TestClient) -> None:
    """Conflicts when the resolver is already running should surface a 409."""

    stub = StubResolverService(start_error=ResolverAlreadyRunningError("already running"))
    client.app.state.app_state.resolver_service = stub

    response = client.post("/resolver/start")

    assert response.status_code == 409
    assert response.json()["detail"] == "already running"


def test_resolver_stop_terminates_process(client: TestClient) -> None:
    """POST /resolver/stop should terminate the managed process."""

    stub = StubResolverService(
        stop_status=ResolverProcessStatus(running=False, pid=None, exit_code=0)
    )
    client.app.state.app_state.resolver_service = stub

    response = client.post("/resolver/stop")

    assert response.status_code == 200
    assert response.json() == {"running": False, "pid": None, "exit_code": 0}


def test_resolver_stop_conflict_returns_409(client: TestClient) -> None:
    """Conflicts when stopping a non-running process should yield a 409."""

    stub = StubResolverService(stop_error=ResolverNotRunningError("not running"))
    client.app.state.app_state.resolver_service = stub

    response = client.post("/resolver/stop")

    assert response.status_code == 409
    assert response.json()["detail"] == "not running"


def test_resolver_status_returns_payload(client: TestClient) -> None:
    """GET /resolver/status should expose the tracked process state."""

    stub = StubResolverService(
        status_payload=ResolverProcessStatus(running=False, pid=None, exit_code=2)
    )
    client.app.state.app_state.resolver_service = stub

    response = client.get("/resolver/status")

    assert response.status_code == 200
    assert response.json() == {"running": False, "pid": None, "exit_code": 2}


class StubResolverService:
    """Helper stub that records resolver health calls."""

    def __init__(
        self,
        payload: dict[str, object] | None = None,
        error: Exception | None = None,
        *,
        start_status: ResolverProcessStatus | None = None,
        start_error: Exception | None = None,
        stop_status: ResolverProcessStatus | None = None,
        stop_error: Exception | None = None,
        status_payload: ResolverProcessStatus | None = None,
    ) -> None:
        self.payload = payload or {"status": "ok"}
        self.error = error
        self.calls: list[str] = []
        self.start_calls: list[str] = []
        self.start_status = start_status
        self.start_error = start_error
        self.stop_status = stop_status
        self.stop_error = stop_error
        self.status_payload = status_payload or ResolverProcessStatus(
            running=False, pid=None, exit_code=None
        )

    def health(self, base_url: str) -> dict[str, object]:
        self.calls.append(base_url)
        if self.error:
            raise self.error
        return dict(self.payload)

    def start_process(self, *, resolver_url: str) -> ResolverProcessStatus:
        self.start_calls.append(resolver_url)
        if self.start_error:
            raise self.start_error
        if self.start_status is None:
            raise AssertionError("start_status must be set for start_process tests")
        return self.start_status

    def stop_process(self) -> ResolverProcessStatus:
        if self.stop_error:
            raise self.stop_error
        if self.stop_status is None:
            raise AssertionError("stop_status must be set for stop_process tests")
        return self.stop_status

    def process_status(self) -> ResolverProcessStatus:
        return self.status_payload
