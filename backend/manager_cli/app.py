"""Command line interface for the Streamarr Manager API."""
from __future__ import annotations

import json
from typing import Optional

import typer

from .client import create_client


DEFAULT_API_BASE = "http://localhost:8000"

app = typer.Typer(help="Interact with the Streamarr Manager backend service.")
config_app = typer.Typer(help="Manage resolver configuration.")
app.add_typer(config_app, name="config")
jobs_app = typer.Typer(help="Inspect and trigger manager jobs.")
app.add_typer(jobs_app, name="jobs")


def _api_base_option() -> typer.Option:
    return typer.Option(
        DEFAULT_API_BASE,
        "--api-base",
        help="Base URL for the Manager API service.",
        show_default=True,
        envvar="STREAMARR_MANAGER_API_BASE",
    )


@app.command()
def health(api_base: str = _api_base_option()) -> None:
    """Call the /health endpoint and pretty-print the response."""

    with create_client(api_base) as client:
        response = client.get("/health")
        response.raise_for_status()
        typer.echo(json.dumps(response.json(), indent=2, ensure_ascii=False))


@config_app.command("show")
def show_config(api_base: str = _api_base_option()) -> None:
    """Display the persisted manager configuration."""

    with create_client(api_base) as client:
        response = client.get("/config")
        response.raise_for_status()
        typer.echo(json.dumps(response.json(), indent=2, ensure_ascii=False))


@config_app.command("update")
def update_config(
    resolver_url: Optional[str] = typer.Option(None, help="Resolver service base URL."),
    strm_output_path: Optional[str] = typer.Option(None, help="Default STRM output directory."),
    tmdb_api_key: Optional[str] = typer.Option(None, help="TMDB API key to persist."),
    clear_tmdb_api_key: bool = typer.Option(
        False,
        "--clear-tmdb-api-key/--no-clear-tmdb-api-key",
        help="Remove the persisted TMDB API key.",
        show_default=False,
    ),
    html_title_fetch: Optional[bool] = typer.Option(
        None,
        "--html-title-fetch/--no-html-title-fetch",
        help="Toggle HTML title fallback.",
        show_default=False,
    ),
    api_base: str = _api_base_option(),
) -> None:
    """Update configuration fields with the provided values."""

    if tmdb_api_key is not None and clear_tmdb_api_key:
        typer.echo("Cannot set and clear the TMDB API key in the same command.", err=True)
        raise typer.Exit(code=1)

    payload: dict[str, object] = {}
    if resolver_url is not None:
        payload["resolver_url"] = resolver_url
    if strm_output_path is not None:
        payload["strm_output_path"] = strm_output_path
    if clear_tmdb_api_key:
        payload["tmdb_api_key"] = None
    elif tmdb_api_key is not None:
        payload["tmdb_api_key"] = tmdb_api_key
    if html_title_fetch is not None:
        payload["html_title_fetch"] = html_title_fetch

    if not payload:
        typer.echo("No updates supplied.")
        raise typer.Exit(code=1)

    with create_client(api_base) as client:
        response = client.put("/config", json=payload)
        response.raise_for_status()
        typer.echo(json.dumps(response.json(), indent=2, ensure_ascii=False))


@jobs_app.command("run")
def run_job(
    job_type: str = typer.Argument(..., help="Job type to execute (collect, catalog, export, etc.)."),
    payload: Optional[str] = typer.Option(
        None,
        "--payload",
        help="Optional JSON payload passed to the job runner.",
    ),
    api_base: str = _api_base_option(),
) -> None:
    """Trigger a job execution via the Manager API."""

    request_body: dict[str, object] = {"type": job_type}
    if payload is not None:
        try:
            request_body["payload"] = json.loads(payload)
        except json.JSONDecodeError as exc:  # pragma: no cover - user input path
            typer.echo(f"Invalid JSON payload: {exc}", err=True)
            raise typer.Exit(code=1) from exc

    with create_client(api_base) as client:
        response = client.post("/jobs/run", json=request_body)
        response.raise_for_status()
        typer.echo(json.dumps(response.json(), indent=2, ensure_ascii=False))


@jobs_app.command("list")
def list_jobs(
    limit: int = typer.Option(10, min=1, max=100, help="Number of recent jobs to display."),
    api_base: str = _api_base_option(),
) -> None:
    """Display recent jobs stored by the manager."""

    with create_client(api_base) as client:
        response = client.get("/jobs", params={"limit": limit})
        response.raise_for_status()
        typer.echo(json.dumps(response.json(), indent=2, ensure_ascii=False))
