"""HTTP client helpers for the Manager CLI."""
from __future__ import annotations

import httpx


def create_client(base_url: str, *, timeout: float = 10.0, transport: httpx.BaseTransport | None = None) -> httpx.Client:
    """Instantiate an HTTPX client with a configurable base URL."""

    return httpx.Client(base_url=base_url, timeout=timeout, transport=transport)
