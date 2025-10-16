"""Resolver integration helpers for the Manager API."""
from __future__ import annotations

from dataclasses import dataclass
import os
import subprocess
import sys
import threading
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx


@dataclass(slots=True)
class ResolverProcessStatus:
    """Represents the lifecycle state of the managed resolver process."""

    running: bool
    pid: int | None
    exit_code: int | None


class ResolverServiceError(RuntimeError):
    """Raised when the manager cannot communicate with or manage the resolver."""


class ResolverAlreadyRunningError(ResolverServiceError):
    """Raised when attempting to start a resolver process that is already running."""


class ResolverNotRunningError(ResolverServiceError):
    """Raised when attempting to stop a resolver process that is not running."""


class ResolverService:
    """Utility wrapper that proxies and manages the resolver service."""

    def __init__(self, *, timeout: float = 5.0) -> None:
        self._timeout = timeout
        self._lock = threading.Lock()
        self._process: subprocess.Popen[bytes] | None = None
        self._last_exit_code: int | None = None

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

    # ------------------------------------------------------------------
    # Process management helpers

    def _parse_port(self, resolver_url: str) -> int:
        parsed = urlparse(resolver_url)
        if parsed.port is not None:
            return parsed.port
        if parsed.scheme == "https":
            return 443
        if parsed.scheme == "http":
            return 80
        return 5055

    def start_process(self, *, resolver_url: str) -> ResolverProcessStatus:
        """Launch the resolver Flask process if it is not already running."""

        with self._lock:
            if self._process and self._process.poll() is None:
                raise ResolverAlreadyRunningError("Resolver process already running")

            port = self._parse_port(resolver_url)
            env = os.environ.copy()
            env.setdefault("RESOLVER_PORT", str(port))

            try:
                process = subprocess.Popen(
                    [sys.executable, "-m", "backend.resolver.api"],
                    env=env,
                )
            except OSError as exc:  # pragma: no cover - spawn failure path
                raise ResolverServiceError(f"Failed to launch resolver: {exc}") from exc

            self._process = process
            self._last_exit_code = None
            return ResolverProcessStatus(running=True, pid=process.pid, exit_code=None)

    def stop_process(self, *, timeout: float = 10.0) -> ResolverProcessStatus:
        """Terminate the managed resolver process if running."""

        with self._lock:
            if self._process is None:
                raise ResolverNotRunningError("Resolver process is not running")

            process = self._process
            if process.poll() is not None:
                self._last_exit_code = process.returncode
                self._process = None
                raise ResolverNotRunningError("Resolver process already stopped")

            process.terminate()
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=timeout)

            self._last_exit_code = process.returncode
            self._process = None
            return ResolverProcessStatus(running=False, pid=None, exit_code=process.returncode)

    def process_status(self) -> ResolverProcessStatus:
        """Return the most recent status for the managed resolver process."""

        with self._lock:
            if self._process is not None:
                exit_code = self._process.poll()
                if exit_code is None:
                    return ResolverProcessStatus(
                        running=True,
                        pid=self._process.pid,
                        exit_code=None,
                    )
                self._last_exit_code = exit_code
                self._process = None

            return ResolverProcessStatus(running=False, pid=None, exit_code=self._last_exit_code)
