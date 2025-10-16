"""Tests for the Typer-based manager CLI."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.manager_api import create_app
from backend.manager_api.settings import ManagerSettings
import importlib

from backend.manager_cli import app as cli_app
cli_app_module = importlib.import_module("backend.manager_cli.app")
from backend.manager_cli import client as client_module


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
