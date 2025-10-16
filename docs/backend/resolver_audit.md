# Backend Resolver Audit

## Overview
The existing `backend/resolver` package delivers the Flask-based playback resolver. The modules below are potential reuse points for the Phase 1 FastAPI service.

## Module Breakdown
- **`api.py`** – Bootstraps the Flask app, exposes catalog/resolve endpoints, manages token caching, and orchestrates proxy relay logic. Reusable helpers include variant scoring (`_variant_sort_key`) and catalog lookup utilities.
- **`catalog.py`** – Provides catalog loading and entry lookup helpers that can be imported directly into the FastAPI service for read-only library queries.
- **`stream_resolver.py`** – Hosts the core `resolve_stream` function that negotiates playable streams per site; useful for `/play` and `/resolver` passthrough endpoints.
- **`metadata_fetcher.py`** – Contains enrichment helpers (HTML title, TMDB) that can be wrapped in future background jobs.
- **`scrapers/`** – Houses site-specific Playwright scrapers used during pipeline runs; Phase 1 API should treat these as worker dependencies rather than HTTP handlers.

## Integration Notes
- Environment variables such as `CATALOG_PATH`, `PROXY_BASE_URL`, and `RESOLVER_PORT` need to be surfaced through the new settings layer so both services stay in sync.
- Token caching is currently in-memory; Phase 1 can re-export existing helpers while Phase 1.5 introduces a shared store via Redis.
- Catalog interactions rely on JSON payloads on disk; introducing a repository abstraction will smooth the transition to SQLite later in Phase 1.
