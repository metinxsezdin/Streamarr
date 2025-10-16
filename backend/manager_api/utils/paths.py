"""Filesystem helpers for manager configuration paths."""
from __future__ import annotations

from pathlib import Path

from platformdirs import user_data_dir


APP_NAME = "Streamarr"
APP_AUTHOR = "Streamarr"


def default_strm_output_path() -> str:
    """Return the platform-appropriate default STRM export directory."""

    base_dir = Path(user_data_dir(APP_NAME, APP_AUTHOR))
    return str(base_dir / "strm")


def ensure_strm_directory(path: str) -> str:
    """Expand and create the STRM directory if it does not exist."""

    resolved = Path(path).expanduser()
    resolved.mkdir(parents=True, exist_ok=True)
    return str(resolved.resolve())
