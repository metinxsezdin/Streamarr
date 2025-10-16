"""CLI entry point for launching the Manager API with Uvicorn."""
import uvicorn

from .app import create_app


def main() -> None:
    """Start a development server for the Manager API."""
    uvicorn.run(create_app(), host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
