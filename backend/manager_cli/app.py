"""Command line interface for the Streamarr Manager API."""
from __future__ import annotations

import json
from typing import List, Literal, Optional

import typer

from .client import create_client


DEFAULT_API_BASE = "http://localhost:8000"

app = typer.Typer(help="Interact with the Streamarr Manager backend service.")
config_app = typer.Typer(help="Manage resolver configuration.")
app.add_typer(config_app, name="config")
jobs_app = typer.Typer(help="Inspect and trigger manager jobs.")
app.add_typer(jobs_app, name="jobs")
library_app = typer.Typer(help="Browse resolver library metadata.")
app.add_typer(library_app, name="library")
resolver_app = typer.Typer(help="Interact with the resolver service via the manager API.")
app.add_typer(resolver_app, name="resolver")


JOB_STATUS_CHOICES = {"queued", "running", "completed", "failed", "cancelled"}


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


@app.command()
def setup(
    resolver_url: str = typer.Option(..., help="Resolver service base URL."),
    strm_output_path: str = typer.Option(..., help="Default STRM export directory."),
    tmdb_api_key: Optional[str] = typer.Option(None, help="TMDB API key to persist."),
    html_title_fetch: bool = typer.Option(
        True,
        "--html-title-fetch/--no-html-title-fetch",
        help="Toggle HTML title fallback for catalog builds.",
        show_default=True,
    ),
    run_initial_job: bool = typer.Option(
        False,
        "--run-initial-job/--no-run-initial-job",
        help="Trigger a bootstrap job after saving configuration.",
        show_default=True,
    ),
    initial_job_type: str = typer.Option(
        "bootstrap",
        help="Job type invoked when run-initial-job is enabled.",
        show_default=True,
    ),
    initial_job_payload: Optional[str] = typer.Option(
        None,
        help="Optional JSON payload forwarded to the bootstrap job.",
    ),
    api_base: str = _api_base_option(),
) -> None:
    """Persist initial configuration and optionally trigger a bootstrap job."""

    payload: dict[str, object] = {
        "resolver_url": resolver_url,
        "strm_output_path": strm_output_path,
        "html_title_fetch": html_title_fetch,
        "run_initial_job": run_initial_job,
        "initial_job_type": initial_job_type,
    }

    if tmdb_api_key is not None:
        payload["tmdb_api_key"] = tmdb_api_key

    if initial_job_payload is not None:
        try:
            payload["initial_job_payload"] = json.loads(initial_job_payload)
        except json.JSONDecodeError as exc:  # pragma: no cover - user input path
            typer.echo(f"Invalid JSON payload: {exc}", err=True)
            raise typer.Exit(code=1) from exc

    with create_client(api_base) as client:
        response = client.post("/setup", json=payload)
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
    statuses: Optional[List[str]] = typer.Option(
        None,
        "--status",
        help="Filter results to specific job statuses (repeat the flag).",
    ),
    job_type: Optional[str] = typer.Option(
        None,
        "--type",
        help="Filter results to a specific job type.",
    ),
    api_base: str = _api_base_option(),
) -> None:
    """Display recent jobs stored by the manager."""

    params: dict[str, object] = {"limit": limit}
    if statuses:
        normalized_statuses: list[str] = []
        for status in statuses:
            value = status.lower()
            if value not in JOB_STATUS_CHOICES:
                typer.echo(
                    "Invalid status value. Allowed values: "
                    + ", ".join(sorted(JOB_STATUS_CHOICES)),
                    err=True,
                )
                raise typer.Exit(code=1)
            normalized_statuses.append(value)
        params["status"] = normalized_statuses
    if job_type:
        params["type"] = job_type

    with create_client(api_base) as client:
        response = client.get("/jobs", params=params)
        response.raise_for_status()
        typer.echo(json.dumps(response.json(), indent=2, ensure_ascii=False))


@jobs_app.command("show")
def show_job(
    job_id: str = typer.Argument(..., help="Identifier of the job to display."),
    api_base: str = _api_base_option(),
) -> None:
    """Display details for a single job."""

    with create_client(api_base) as client:
        response = client.get(f"/jobs/{job_id}")
        if response.status_code == 404:
            typer.echo("Job not found", err=True)
            raise typer.Exit(code=1)
        response.raise_for_status()
        typer.echo(json.dumps(response.json(), indent=2, ensure_ascii=False))


@jobs_app.command("cancel")
def cancel_job(
    job_id: str = typer.Argument(..., help="Identifier of the job to cancel."),
    reason: Optional[str] = typer.Option(
        None,
        "--reason",
        help="Optional reason recorded with the cancellation.",
    ),
    api_base: str = _api_base_option(),
) -> None:
    """Cancel a queued or running job via the Manager API."""

    payload: dict[str, object] | None = None
    if reason is not None:
        payload = {"reason": reason}

    with create_client(api_base) as client:
        if payload is None:
            response = client.post(f"/jobs/{job_id}/cancel")
        else:
            response = client.post(f"/jobs/{job_id}/cancel", json=payload)
        if response.status_code == 404:
            typer.echo("Job not found", err=True)
            raise typer.Exit(code=1)
        response.raise_for_status()
        typer.echo(json.dumps(response.json(), indent=2, ensure_ascii=False))


@jobs_app.command("logs")
def job_logs(
    job_id: str = typer.Argument(..., help="Identifier of the job to inspect."),
    limit: int = typer.Option(50, min=1, max=500, help="Maximum number of log entries."),
    api_base: str = _api_base_option(),
) -> None:
    """Display persisted log events for a job."""

    params = {"limit": limit}
    with create_client(api_base) as client:
        response = client.get(f"/jobs/{job_id}/logs", params=params)
        if response.status_code == 404:
            typer.echo("Job not found", err=True)
            raise typer.Exit(code=1)
        response.raise_for_status()
        typer.echo(json.dumps(response.json(), indent=2, ensure_ascii=False))


@library_app.command("list")
def list_library(
    page: int = typer.Option(1, min=1, help="Page number starting at 1."),
    page_size: int = typer.Option(25, min=1, max=100, help="Number of items per page."),
    query: Optional[str] = typer.Option(None, help="Optional title search term."),
    sites: Optional[list[str]] = typer.Option(
        None,
        "--site",
        "-s",
        help="Filter results to one or more source sites (repeat the flag).",
    ),
    item_type: Optional[str] = typer.Option(
        None, help="Filter results by item type (movie or episode)."
    ),
    year: Optional[int] = typer.Option(
        None,
        min=1800,
        max=3000,
        help="Filter results by an exact release year.",
    ),
    year_min: Optional[int] = typer.Option(
        None,
        min=1800,
        max=3000,
        help="Filter results to items released on or after this year.",
    ),
    year_max: Optional[int] = typer.Option(
        None,
        min=1800,
        max=3000,
        help="Filter results to items released on or before this year.",
    ),
    has_tmdb: Optional[bool] = typer.Option(
        None,
        "--has-tmdb/--no-has-tmdb",
        help="Filter by presence of TMDB metadata.",
        show_default=False,
    ),
    sort: Literal[
        "updated_desc",
        "updated_asc",
        "title_asc",
        "title_desc",
        "year_desc",
        "year_asc",
    ] = typer.Option(
        "updated_desc",
        help="Sort ordering applied to results.",
        show_default=True,
    ),
    api_base: str = _api_base_option(),
) -> None:
    """Display library metadata returned by the Manager API."""

    params: dict[str, object] = {"page": page, "page_size": page_size, "sort": sort}
    if query:
        params["query"] = query
    if sites:
        params["site"] = sites
    if item_type:
        params["item_type"] = item_type
    if year is not None:
        params["year"] = year
    if year_min is not None:
        params["year_min"] = year_min
    if year_max is not None:
        params["year_max"] = year_max
    if has_tmdb is not None:
        params["has_tmdb"] = has_tmdb

    with create_client(api_base) as client:
        response = client.get("/library", params=params)
        response.raise_for_status()
        typer.echo(json.dumps(response.json(), indent=2, ensure_ascii=False))


@library_app.command("show")
def show_library_item(
    item_id: str = typer.Argument(..., help="Library item identifier to display."),
    api_base: str = _api_base_option(),
) -> None:
    """Display details for a single library item."""

    with create_client(api_base) as client:
        response = client.get(f"/library/{item_id}")
        response.raise_for_status()
        typer.echo(json.dumps(response.json(), indent=2, ensure_ascii=False))


@library_app.command("metrics")
def library_metrics(api_base: str = _api_base_option()) -> None:
    """Display aggregate library statistics for dashboards."""

    with create_client(api_base) as client:
        response = client.get("/library/metrics")
        response.raise_for_status()
        typer.echo(json.dumps(response.json(), indent=2, ensure_ascii=False))


@resolver_app.command("health")
def resolver_health(api_base: str = _api_base_option()) -> None:
    """Display the proxied resolver health payload."""

    with create_client(api_base) as client:
        response = client.get("/resolver/health")
        response.raise_for_status()
        typer.echo(json.dumps(response.json(), indent=2, ensure_ascii=False))


@resolver_app.command("start")
def resolver_start(api_base: str = _api_base_option()) -> None:
    """Start the resolver process managed by the API service."""

    with create_client(api_base) as client:
        response = client.post("/resolver/start")
        response.raise_for_status()
        typer.echo(json.dumps(response.json(), indent=2, ensure_ascii=False))


@resolver_app.command("stop")
def resolver_stop(api_base: str = _api_base_option()) -> None:
    """Stop the resolver process managed by the API service."""

    with create_client(api_base) as client:
        response = client.post("/resolver/stop")
        response.raise_for_status()
        typer.echo(json.dumps(response.json(), indent=2, ensure_ascii=False))


@resolver_app.command("status")
def resolver_status(api_base: str = _api_base_option()) -> None:
    """Display the resolver process status tracked by the manager."""

    with create_client(api_base) as client:
        response = client.get("/resolver/status")
        response.raise_for_status()
        typer.echo(json.dumps(response.json(), indent=2, ensure_ascii=False))
