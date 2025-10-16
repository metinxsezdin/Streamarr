"""Resolver integration helpers for the Manager API."""
from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import httpx


class ResolverServiceError(RuntimeError):
    """Raised when the manager cannot communicate with the resolver service."""


class ResolverService:
    """Utility wrapper that proxies requests to the existing resolver."""

    def __init__(self, *, timeout: float = 5.0) -> None:
        self._timeout = timeout

    def _build_url(self, base_url: str, path: str) -> str:
        normalized_base = base_url.rstrip("/") + "/"
        return urljoin(normalized_base, path)

    def health(self, base_url: str) -> dict[str, Any]:
        """Fetch the resolver /health payload and return the JSON body."""

        url = self._build_url(base_url, "health")
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(url)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:  # pragma: no cover - network error path
            raise ResolverServiceError(
                f"Resolver responded with HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:  # pragma: no cover - network error path
            raise ResolverServiceError(f"Failed to contact resolver: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:  # pragma: no cover - invalid JSON path
            raise ResolverServiceError("Resolver returned invalid JSON") from exc

        if not isinstance(payload, dict):
            raise ResolverServiceError("Resolver health response must be an object")

        return payload
