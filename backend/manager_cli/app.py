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
    html_title_fetch: Optional[bool] = typer.Option(
        None,
        "--html-title-fetch/--no-html-title-fetch",
        help="Toggle HTML title fallback.",
        show_default=False,
    ),
    api_base: str = _api_base_option(),
) -> None:
    """Update configuration fields with the provided values."""

    payload: dict[str, object] = {}
    if resolver_url is not None:
        payload["resolver_url"] = resolver_url
    if strm_output_path is not None:
        payload["strm_output_path"] = strm_output_path
    if tmdb_api_key is not None:
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
