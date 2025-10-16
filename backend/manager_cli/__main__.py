"""Console entry point for the manager CLI."""
from __future__ import annotations

from .app import app


def main() -> None:
    """Execute the Typer application."""

    app()


if __name__ == "__main__":
    main()
