"""Tests for the Typer-based manager CLI."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import importlib

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner
from sqlmodel import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.manager_api import create_app  # noqa: E402
from backend.manager_api.settings import ManagerSettings  # noqa: E402
from backend.manager_api.models import LibraryItemRecord  # noqa: E402
from backend.manager_cli import app as cli_app  # noqa: E402
from backend.manager_cli import client as client_module  # noqa: E402


class StubResolverService:
    """Simple stub for the resolver service dependency."""

    def __init__(self, payload: dict[str, object] | None = None, error: Exception | None = None) -> None:
        self.payload = payload or {"status": "ok"}
        self.error = error
        self.calls: list[str] = []

    def health(self, base_url: str) -> dict[str, object]:
        self.calls.append(base_url)
        if self.error:
            raise self.error
        return dict(self.payload)

cli_app_module = importlib.import_module("backend.manager_cli.app")


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def cli_client(tmp_path: Path) -> TestClient:
    """Provide a TestClient and patch the CLI HTTP client factory."""

    db_path = tmp_path / "manager.db"
    settings = ManagerSettings(database_url=f"sqlite:///{db_path}")
    app = create_app(settings=settings)
    test_client = TestClient(app)

    original_factory = client_module.create_client
    original_app_factory = cli_app_module.create_client

    def _factory(base_url: str, *, timeout: float = 10.0, transport: Any = None):  # type: ignore[override]
        return test_client

    client_module.create_client = _factory  # type: ignore[assignment]
    cli_app_module.create_client = _factory  # type: ignore[assignment]

    yield test_client

    client_module.create_client = original_factory  # type: ignore[assignment]
    cli_app_module.create_client = original_app_factory  # type: ignore[assignment]


def _seed_library(cli_client: TestClient) -> None:
    app_state = cli_client.app.state.app_state
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
            )
        )
        session.commit()


def test_cli_health_command_outputs_status(runner: CliRunner, cli_client: TestClient) -> None:
    """The health command should display OK status."""

    result = runner.invoke(cli_app, ["health"])

    assert result.exit_code == 0
    assert "\"status\": \"ok\"" in result.output


def test_cli_config_update_modifies_store(runner: CliRunner, cli_client: TestClient) -> None:
    """Config update command should persist changes and print them."""

    result = runner.invoke(
        cli_app,
        [
            "config",
            "update",
            "--resolver-url",
            "http://resolver.internal:5055",
            "--strm-output-path",
            "/data/strm",
            "--no-html-title-fetch",
        ],
    )

    assert result.exit_code == 0
    assert "resolver.internal" in result.output
    assert "\"html_title_fetch\": false" in result.output

    persisted = cli_client.get("/config").json()
    assert persisted["html_title_fetch"] is False
    assert persisted["strm_output_path"] == "/data/strm"


def test_cli_config_update_can_clear_tmdb_api_key(
    runner: CliRunner, cli_client: TestClient
) -> None:
    """The CLI should allow clearing the stored TMDB API key."""

    seed_result = runner.invoke(
        cli_app,
        [
            "config",
            "update",
            "--tmdb-api-key",
            "temporary-token",
        ],
    )

    assert seed_result.exit_code == 0
    assert "temporary-token" in seed_result.output
    assert cli_client.get("/config").json()["tmdb_api_key"] == "temporary-token"

    clear_result = runner.invoke(cli_app, ["config", "update", "--clear-tmdb-api-key"])

    assert clear_result.exit_code == 0
    assert "\"tmdb_api_key\": null" in clear_result.output
    assert cli_client.get("/config").json()["tmdb_api_key"] is None


def test_cli_jobs_run_creates_completed_job(runner: CliRunner, cli_client: TestClient) -> None:
    """jobs run command should trigger a completed job."""

    result = runner.invoke(
        cli_app,
        ["jobs", "run", "collect", "--payload", '{"refresh": true}'],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "completed"
    assert payload["payload"] == {"refresh": True}
    assert payload["worker_id"] == "manager-api"
    assert payload["duration_seconds"] >= 0
    assert "created_at" in payload

    jobs = cli_client.get("/jobs").json()
    assert any(job["type"] == "collect" for job in jobs)


def test_cli_jobs_list_outputs_recent_jobs(runner: CliRunner, cli_client: TestClient) -> None:
    """jobs list command should display stored jobs."""

    cli_client.post("/jobs/run", json={"type": "catalog"})

    result = runner.invoke(cli_app, ["jobs", "list", "--limit", "5"])

    assert result.exit_code == 0
    assert "\"status\": \"completed\"" in result.output


def test_cli_jobs_list_supports_filters(runner: CliRunner, cli_client: TestClient) -> None:
    """jobs list should forward status and type filters to the API."""

    cli_client.post("/jobs/run", json={"type": "collect"})
    cli_client.post("/jobs/run", json={"type": "catalog"})

    result = runner.invoke(
        cli_app,
        [
            "jobs",
            "list",
            "--status",
            "completed",
            "--type",
            "collect",
        ],
    )

    assert result.exit_code == 0
    assert "\"type\": \"collect\"" in result.output
    assert "\"type\": \"catalog\"" not in result.output


def test_cli_jobs_show_displays_single_job(runner: CliRunner, cli_client: TestClient) -> None:
    """jobs show should fetch job details from the API."""

    response = cli_client.post(
        "/jobs/run",
        json={"type": "collect", "payload": {"full": True}},
    )
    job_id = response.json()["id"]

    result = runner.invoke(cli_app, ["jobs", "show", job_id])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["id"] == job_id
    assert payload["payload"] == {"full": True}
    assert payload["worker_id"] == "manager-api"
    assert payload["duration_seconds"] >= 0


def test_cli_jobs_show_handles_missing_job(
    runner: CliRunner, cli_client: TestClient
) -> None:
    """jobs show should exit with an error when the job is not found."""

    _ = cli_client
    result = runner.invoke(cli_app, ["jobs", "show", "missing-id"])

    assert result.exit_code == 1
    assert "Job not found" in result.output


def test_cli_jobs_cancel_marks_job_cancelled(
    runner: CliRunner, cli_client: TestClient
) -> None:
    """jobs cancel should mark the job as cancelled and display it."""

    app_state = cli_client.app.state.app_state
    job = app_state.job_store.enqueue("collect")

    result = runner.invoke(
        cli_app,
        ["jobs", "cancel", job.id, "--reason", "user requested"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "cancelled"
    assert payload["error_message"] == "user requested"
    assert payload["duration_seconds"] is None


def test_cli_jobs_cancel_handles_missing_job(
    runner: CliRunner, cli_client: TestClient
) -> None:
    """jobs cancel should exit with an error when the job is not found."""

    _ = cli_client
    result = runner.invoke(cli_app, ["jobs", "cancel", "missing-id"])

    assert result.exit_code == 1
    assert "Job not found" in result.output


def test_cli_library_list_outputs_metadata(
    runner: CliRunner, cli_client: TestClient
) -> None:
    """library list command should render library results."""

    _seed_library(cli_client)

    result = runner.invoke(cli_app, ["library", "list", "--page-size", "1"])

    assert result.exit_code == 0
    assert "\"total\": 2" in result.output


def test_cli_library_metrics_outputs_statistics(
    runner: CliRunner, cli_client: TestClient
) -> None:
    """library metrics command should render aggregate counts."""

    _seed_library(cli_client)

    result = runner.invoke(cli_app, ["library", "metrics"])

    assert result.exit_code == 0
    assert "\"total\": 2" in result.output
    assert "\"tmdb_enriched\": 1" in result.output


def test_cli_library_list_supports_filters(
    runner: CliRunner, cli_client: TestClient
) -> None:
    """library list command should forward optional filters to the API."""

    _seed_library(cli_client)

    result = runner.invoke(
        cli_app,
        [
            "library",
            "list",
            "--site",
            "dizipal",
            "--item-type",
            "episode",
            "--year",
            "2019",
            "--year-min",
            "2010",
            "--year-max",
            "2019",
            "--no-has-tmdb",
        ],
    )

    assert result.exit_code == 0
    assert "\"total\": 1" in result.output
    assert "episode-1" in result.output


def test_cli_library_list_supports_multiple_sites_and_sort(
    runner: CliRunner, cli_client: TestClient
) -> None:
    """library list should accept repeated site filters and custom sort order."""

    _seed_library(cli_client)

    result = runner.invoke(
        cli_app,
        [
            "library",
            "list",
            "--site",
            "dizibox",
            "--site",
            "dizipal",
            "--sort",
            "title_desc",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [item["id"] for item in payload["items"]] == [
        "episode-1",
        "movie-1",
    ]


def test_cli_library_show_outputs_item_detail(
    runner: CliRunner, cli_client: TestClient
) -> None:
    """library show command should render item details."""

    _seed_library(cli_client)

    result = runner.invoke(cli_app, ["library", "show", "movie-1"])

    assert result.exit_code == 0
    assert "Example Movie" in result.output


def test_cli_resolver_health_outputs_payload(
    runner: CliRunner, cli_client: TestClient
) -> None:
    """resolver health command should print the resolver payload."""

    stub = StubResolverService(payload={"status": "ok", "cache_size": 7})
    cli_client.app.state.app_state.resolver_service = stub

    result = runner.invoke(cli_app, ["resolver", "health"])

    assert result.exit_code == 0
    assert "\"cache_size\": 7" in result.output
    assert stub.calls == ["http://localhost:5055"]
