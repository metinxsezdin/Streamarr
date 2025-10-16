# ADR 0001: Manager API Foundation

## Status
Accepted – 2025-10-17

## Context
The Streamarr manager initiative requires a backend service that exposes
configuration, job orchestration, and resolver controls through a modern API.
Early sprint work scaffolded a FastAPI application with in-memory state, but
the roadmap calls for durable configuration, a CLI surface, and development
tooling that mirrors future production expectations. To support subsequent
sprints, we need a persistent data layer, a reproducible OpenAPI contract, and
automation-friendly entry points.

## Decision
- Adopt SQLModel with SQLite as the initial persistence layer for manager
  configuration and job metadata. Default settings point at `./data/manager.db`
  while allowing overrides through environment variables.
- Initialize the database during application startup, seeding a default
  configuration derived from environment-backed settings.
- Expose configuration via a thread-safe store that mediates SQLModel sessions
  so API handlers and the CLI share a common persistence mechanism.
- Provide a Typer-based CLI (`backend.manager_cli`) with `health` and
  `config` commands to exercise the API, enabling parity checks with the future
  UI and automation scripts.
- Document the HTTP contract in `docs/backend/manager_api_openapi.yaml` to guide
  router implementation and front-end client generation.
- Add a backend `Makefile` with standard `dev`, `lint`, and `test` targets
  aligned with Ruff and pytest to streamline local workflows.

## Consequences
- SQLite provides immediate durability without introducing new infrastructure,
  but we must plan a migration path to a production-grade database when the job
  queue arrives (Phase 1.5).
- SQLModel introduces an additional dependency; contributors must install it
  alongside the existing FastAPI stack and learn its declarative patterns.
- The CLI requires Typer and HTTPX, modestly expanding the runtime footprint,
  yet it gives us a vehicle for regression testing and developer ergonomics.
- Maintaining the OpenAPI spec alongside implementation demands discipline,
  ensuring schema updates occur with code changes to keep clients in sync.
- Ruff is now part of the toolchain; CI and local environments need the
  dependency available for linting even if enforcement begins later.
