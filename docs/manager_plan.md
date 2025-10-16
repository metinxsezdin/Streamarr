# Streamarr Manager (Expo) Plan

## Overview
Create a cross-platform control panel for Streamarr using Expo (React Native) for the frontend and a FastAPI-based backend (existing resolver + new management endpoints). The Manager will allow users to configure Streamarr, run data pipelines, observe library status, and operate the resolver from a user-friendly interface.

## Goals
- Reduce manual CLI workflow to guided UI flows.
- Provide visibility into link collection, catalog builds, STRM exports, and resolver performance.
- Make onboarding simple: first-run wizard collects required config and optionally runs the full pipeline.
- Support mobile (iOS/Android) and web clients using a single Expo codebase.

## Success Metrics
- First-run wizard completes full configuration (resolver host, TMDB key, STRM paths) in under 10 minutes without CLI intervention.
- 95% of pipeline runs triggered from the Manager succeed end-to-end and surface live progress updates within 5 seconds of a state change.
- Job history, logs, and library data are observable from both mobile and web clients with <2 second perceived latency on broadband.
- Auth handshake (token retrieval + refresh) remains below 500ms p95 and persists securely across application restarts.
- Expo web build is deployed alongside backend services before Phase 5 hand-off, with parity on the core dashboard and job controls.

## High-Level Architecture

### Frontend (Expo)
- Managed workflow with TypeScript.
- Navigation: `expo-router` or `react-navigation` with tab navigation (Dashboard, Library, Jobs, Settings, Logs).
- State/data: React Query + Zustand (or Recoil) for API queries and local store.
- UI components: Expo Router screens with styling (Tailwind + `nativewind`, or Chakra UI for RN).
- Build: EAS build for mobile, `expo export --platform web` for web dashboard.

### Backend
- FastAPI service (extend `backend/resolver`) exposing REST and WebSocket endpoints:
  - `/setup`, `/config`
  - `/jobs` (enqueue pipeline tasks, job status)
  - `/library` (paginated film/series info from SQLite)
  - `/logs/stream` (WebSocket for live job logs)
  - `/resolver` (start/stop, health)
- Job runner: start with FastAPI background tasks + SQLite-backed queue, then migrate to Redis-backed RQ/Dramatiq during Phase 1.5.
- Scheduler: APScheduler or RQ Scheduler for recurring jobs.
- Maintain existing resolver API; integrate with new config (CATALOG_PATH, PROXY_BASE_URL).

### Shared Package
- `packages/shared`: TypeScript interfaces, API client, env definitions.
- Provide CLI wrappers (`streamarr` command) that call the new backend endpoints to preserve automation.

## Solo Development Strategy
- **Time blocking & planning**: Allocate weekly focus blocks (backend, frontend, ops) and maintain a single roadmap board to reduce context switching overhead.
- **Documentation first**: Capture architecture notes, ADRs, and onboarding steps in-line so future collaborators or automation scripts can plug in with minimal ramp-up.
- **Automation as force multiplier**: Lean on scaffolding scripts, codegen (OpenAPI, TypeScript types), and CI pipelines to offload repetitive work that a larger team would otherwise absorb.
- **Feedback loop**: Schedule usability checks with target users/early adopters at the end of each phase and collect telemetry to substitute for formal QA bandwidth.
- **Release cadence**: Ship in small increments (feature flags, dark deploys) to minimize rollback pain and keep momentum without manual testers.
- **AI pair programming**: Treat ChatGPT Codex as a collaborative assistant for ideation, boilerplate generation, and reviews while keeping human oversight on design, security, and production releases.

## AI Assistant Collaboration
- **Prompt discipline**: Maintain a prompt log documenting context, constraints, and desired outputs so interactions with ChatGPT Codex stay reproducible and auditable.
- **Workflow cadence**: Use Codex for design spikes, code scaffolding, test generation, and documentation drafts; always run generated code through lint/tests before committing.
- **Guardrails**: Validate AI suggestions against project conventions, security posture, and dependency policies; reject outputs that cannot be explained or justified.
- **Knowledge capture**: Summarize accepted Codex contributions in commit messages and ADRs to preserve rationale beyond the chat transcript.
- **Escalation**: When Codex output conflicts with domain knowledge or tests fail repeatedly, pause and perform manual investigation before re-prompting.

### Prompt Log Template (Markdown friendly)
````markdown
# Codex Prompt Log

- **Date / Time**: YYYY-MM-DD HH:MM (TZ)
- **Feature / Task**: link to roadmap item or issue
- **Context Summary**:
  - Current state / branch:
  - Key constraints (deps, performance, security):
- **Prompt**:
  ```text
  <exact prompt provided to Codex>
  ```
- **Assistant Output Summary**:
  - Proposed solution:
  - Files touched / to create:
  - Follow-up actions requested:
- **Decision**:
  - Accepted / Modified / Rejected (with reason)
- **Validation**:
  - Tests run:
  - Manual checks:
- **Notes / Next Steps**:
  - TODOs:
  - Risks:
```` 

## Engineering Foundations
- Monorepo layout with `apps/expo`, `backend`, `packages/shared`, and `infrastructure` directories; enforce code owners and review paths per area.
- Adopt linting/formatting (ESLint/Prettier for TypeScript, ruff/black for Python) and pre-commit hooks; gate merges on passing unit/integration tests.
- Centralize environment configuration via `.env` templates and typed schema validation (e.g., `zod`); fail fast on missing/invalid runtime variables.
- Instrument backend endpoints with structured logging (JSON), request IDs, and metrics (Prometheus/OpenTelemetry) to power dashboard insights.
- Establish feature flagging mechanism (simple config toggles) for incremental rollout of scheduler, notifications, and resolver controls.

## User Flow / Screens

### 1. Onboarding Wizard
- Run on first launch; collects:
  - Resolver URL / port
  - STRM output path
  - TMDB key, HTML title fetch preference
  - HDFilm sitemap TTL, delay
- Posts config to backend `/setup`.
- Optionally triggers initial pipeline (`collect + catalog + export`).

### 2. Dashboard
- Summary cards: last pipeline run, next scheduled run, resolver status, library counts.
- “Run Pipeline” button with modal for options:
  - with TMDB enrichment
  - HTML title fetch
  - chunk size override
- Quick actions: collect-only, export-only, regenerate STRM.
- Recent job list with status and view log button.

### 3. Library Explorer
- Tab for Movies / Series with search & filter (site, year, TMDB presence).
- Item cards display poster/backdrop (if available), sources, and fallback order.
- Detail view modal:
  - Full metadata (overview, year, TMDB ID).
  - Buttons: “Test playback” (hit `/play/<id>?format=json`), “Regenerate STRM”, “Edit metadata (future)”.
- Integration with resolver to show current best variant chosen (eg. 1080p stream).

### 4. Jobs
- Filter by status (running/completed/failed).
- Job detail view with progress (percent, steps) and log streaming via WebSocket.
- Support cancellation if the queue allows it.
- Historical job stats chart (e.g., average duration).

### 5. Settings
- Forms for:
  - Link collection: sitemap TTL, delay, Dizibox max shows.
  - Catalog builder defaults: chunk size, HTML title fetch, TMDB preference.
  - STRM export: resolver base, output directories.
  - Resolver: port, PROXY_BASE_URL, health check interval.
- Buttons for “Clear HDFilm cache”, “Reset config to defaults”, “Download catalog”.
- Save triggers backend update + immediate effect (reload config in worker/resolver).

### 6. Resolver Control
- Start/stop resolver (subprocess or Docker container).
- Live logs panel, health status indicator.
- Select active catalog (JSON vs SQLite) via dropdown.
- Proxy configuration view (PROXY_BASE_URL, Relay status).

### 7. Logs (optional separate screen)
- List log files (collect, catalog, export, resolver).
- On tap, show tail (subscribe to backend log stream).
- Download log (mobile share sheet, or web download).

## Data & API Contracts
- **Core entities**:
  - `Config`: persisted key/value pairs (resolver host, STRM paths, TMDB key, feature flags) with versioning and audit trail.
  - `Job`: queue metadata (id, type, payload, status, progress, started_at, finished_at, worker_id, error blob).
  - `LibraryItem`: movies/series with variants, availability, enrichment metadata, STRM status, last_seen timestamps.
  - `LogEvent`: structured log entries associated with job_id/resolver_id and severity (info/warn/error).
- **REST endpoints** (FastAPI):
  - `POST /setup` seeds config and schedules optional bootstrap pipeline; returns auth token.
  - `GET/PUT /config` fetches and updates persisted settings with validation and side-effect triggers.
  - `POST /jobs/run` enqueues pipeline jobs with options; `GET /jobs/{id}` returns job detail; `GET /jobs` lists with filters.
  - `GET /library` paginated query with search params; `GET /library/{id}` returns metadata + resolver playback test; `POST /library/{id}/strm` regenerates STRM.
  - `POST /resolver/start` / `/stop` controls resolver process; `GET /resolver/health` exposes status and active catalog.
  - `GET /logs/stream` (upgrade to WebSocket) streams job/resolver logs; `GET /logs/{bucket}` downloads archived logs.
- **WebSocket channels**:
  - `jobs.progress`: emits job status, percent complete, ETA, and worker info.
  - `logs.tail`: streams log lines for active jobs/resolver with rate limiting.
  - `resolver.health`: pushes heartbeat and active catalog updates.
- **Client SDK**: `packages/shared` exports typed API client with query keys, pagination helpers, and error normalization to keep Expo + CLI in sync.

## Automation & Scheduling
- Backend exposes `/jobs/run` for pipeline with options.
- Scheduler (APScheduler or RQ Scheduler):
  - UI to set "Collect daily at 03:00", "Export STRM weekly".
- Job status persisted (SQLite job table).
- Notification system (Expo notifications/push) for job success/failure (optional).
- Support job dependencies, priority, concurrency caps, and manual overrides (e.g., trigger export after current collect finishes) to reflect real-world operational flows.

## Auth & Security
- Initial setup configures admin password or bearer token.
- Backend issues JWT (short-lived) for clients; stored securely (SecureStore on mobile).
- Document future role-based access (viewer/operator/admin) requirements and align with Phase 1.5 deliverables so later expansion doesn't break auth flows.
- Rate limiting for pipeline endpoints to avoid accidental flooding.

## Developer Experience
- Monorepo with pnpm/yarn workspaces.
- Environment management: shared `.env.example` files per package, `dotenv-flow` (or equivalent) for local overrides, and clear guidance on handling secrets/Expo config.
- Observability baseline: OpenTelemetry traces wired through FastAPI + Expo, Prometheus metrics (or StatsD) scraped in dev/staging, and Sentry (or similar) error reporting with dashboard/alert ownership documented.
- Commands:
  - `pnpm dev:backend` - FastAPI + RQ worker
  - `pnpm dev:frontend` - Expo dev server
  - `pnpm dev` - concurrently run both
- Testing strategy:
  - Backend: Pytest for unit + integration (SQLite fixtures), contract tests from OpenAPI schema.
  - Frontend: Jest + React Testing Library for components, Detox/EAS preview for critical flows.
  - End-to-end: Cypress (Expo web) or `@testing-library/react-native` for mobile flows.
- Tooling:
  - Ruff + Black (Python), ESLint + Prettier (TS).
  - Commit hooks via Husky/lint-staged.
- CI (GitHub Actions):
  - Backend: lint, mypy, pytest.
  - Frontend: lint, tests, Expo EAS build (web + Android preview).
  - Cache Expo/EAS artifacts and gate full mobile builds to nightly pipelines to keep PR runs fast.
  - Docker compose smoke test (backend + Redis + worker).
- Release:
  - Backend container pushed to GHCR.
  - Expo web deployed to Netlify/Vercel; optional mobile builds with EAS.
  - Versioned changelog, release automation (semantic-release).
  - Staged rollout plan: preview environments for web, internal/beta tracks for mobile stores, and automated smoke tests before promoting to production.

## Testing & QA Strategy
- **Unit & integration**: prioritize pytest + Jest coverage around config validation, job orchestration, and UI data hooks; add new tests alongside each feature to prevent regression debt.
- **Contract assurance**: automate schema-driven tests (schemathesis/Pact) nightly so CLI, Manager, and resolver contracts stay aligned without manual verification.
- **End-to-end**: maintain a slim Detox/Playwright smoke suite for critical flows (onboarding, job trigger, STRM regeneration) that can run before releases without consuming a full day.
- **Performance & resilience**: schedule lightweight k6 scenarios monthly (or before major releases) to watch for queue saturation, WebSocket drift, and offline fallbacks.
- **Release criteria**: gated on green CI, manual smoke on primary device/browser, and an updated rollback checklist kept in the repo.
- **Codex Output Checklist**:
  - [ ] Capture prompt + response in the log template with context.
  - [ ] Review generated code for security, data handling, and architectural fit.
  - [ ] Run `pnpm lint`, `pnpm test`, `pytest`, or relevant commands on touched packages.
  - [ ] Verify formatting (Prettier/Black) and ensure no TODOs/PLACEHOLDER text remains.
  - [ ] Document acceptance or adjustments in commit message/ADR.

## Deployment & Operations
- Environments: local (docker compose), staging (auto-deploy on main), production (manual promotion with change log and checklist) with scripted provisioning so a single operator can reproduce environments quickly.
- CI/CD: GitHub Actions orchestrates lint/tests, builds Docker images, triggers EAS build profiles, and posts release artifacts; failures ping a single maintainer notification channel.
- Observability: ship structured logs to Loki/CloudWatch, expose Prometheus metrics (job queue depth, resolver health), and trace key flows with OpenTelemetry to surface issues without 24/7 monitoring.
- Secrets/config: `.env` templates for local, secret manager/Key Vault for hosted environments, with rotation reminders tracked in calendar/task system.
- Disaster recovery: nightly catalog/STRM/job-log backups to object storage, restore runbooks tested every quarter, and RPO/RTO targets scoped to what a solo maintainer can support.
- Support playbook: consolidated runbook for resolver outage, queue backlog, and pipeline failures, including canned status updates to reduce triage time.

## Risks & Mitigations
- Single maintainer fatigue -> enforce quarterly maintenance breaks, automate repetitive chores (release scripts, changelog generation), and keep a prioritized backlog to defer non-critical work.
- Queue migration creating downtime -> dual-run SQLite and Redis queues during cutover, with canary workers.
- Mobile/Web UI divergence -> maintain shared component library and visual regression tests (Chromatic/Storybook) to detect drift.
- API surface sprawl -> publish versioned API docs, add backward-compatible deprecation policy, and gate new endpoints behind feature flags.
- Secrets leakage -> enforce `.env` gitignore, integrate secrets scanning (gitleaks) and rotate credentials on detection.
- Performance regressions due to large libraries -> benchmark pagination endpoints, add server-side filtering, and cache heavy queries.
- Onboarding wizard abandonment -> run usability testing on prototypes and add progress save/restore plus contextual help.
- AI hallucination or outdated guidance -> require manual verification of Codex output, cross-check against latest docs, and keep dependency/version matrices up to date.

## Open Questions & Follow-Ups
- Target hosting strategy for FastAPI + queue: self-managed Docker, managed container service, or existing infrastructure?
- Preferred auth provider for future multi-user support (internal accounts vs. integrating with OAuth providers)?
- Minimum viable analytics for dashboard: which KPIs must ship in Phase 1 vs. later analytics work?
- Access model for CLI automation: should Manager expose API tokens for headless scripts or rely on existing CLI auth?
- Localization workflow tooling (e.g., i18next, Phrase) and who owns translation updates each release?
- What workstreams could be handed off to contractors or community contributors if capacity becomes constrained?
- How should Codex interaction notes be stored (repo docs vs. external journal) to preserve decision history without leaking sensitive data?

## Roadmap
1. **Phase 1**: Backend API scaffold + CLI parity
   - FastAPI endpoints for pipeline actions, config, library list.
   - Job orchestrator starts with FastAPI background tasks + SQLite-backed job queue to avoid early Redis dependency.
   - Persistent job log storage (SQLite table).
   - Extend resolver config endpoints (start/stop, status).
   - Rework CLI entry-point to call new API (backward compatibility).
   - Deliverables: API docs (OpenAPI), CLI parity tests.
2. **Phase 1.5**: Queue transition & observability
   - Provision Redis (or preferred broker) locally and in deployment environments, with clear setup docs.
   - Migrate job orchestrator to RQ or Dramatiq and validate worker scaling behaviour.
   - Update docker compose and infrastructure automation to include the queue service.
   - Add queue health checks, metrics, and alerting hooks to surface failures early.
   - Document migration steps for existing CLI users and background task backlog.
3. **Phase 2**: Expo app foundation
   - Setup project, navigation, auth, basic dashboard.
   - First-run wizard: collect backend URL, TMDB key, resolver base.
   - Auth (token issuance, SecureStore persistence).
   - Config screen to POST to backend, validation + error messaging.
   - Basic dashboard cards + pipeline trigger button.
4. **Phase 3**: Library + Jobs modules
   - Library list, detail view, job list/log streaming.
   - STRM regenerate action from UI.
   - Infinite scroll/pagination controls.
   - Skeleton loaders and optimistic updates for key lists to improve perceived performance on slower devices.
   - Search/filter (site, year, metadata presence).
   - Job detail view with WebSocket log streaming, cancel button.
   - "Test playback" action hitting `/play/<id>?format=json` to confirm resolver path.
5. **Phase 4**: Scheduler & notifications
   - UI for cron-like schedules.
   - Optional push notification integration.
   - Backend scheduler (APScheduler/RQ Scheduler) with persistence.
   - CRUD endpoints + UI for schedule management.
   - Notification channel (Expo push/email webhook) per job outcome.
   - Retry/backoff policies for failed jobs, exposed in UI with sensible defaults.
6. **Phase 5**: Polishing & packaging
   - Expo web deployment, mobile builds.
   - Docker compose for backend (FastAPI + Redis + worker).
   - Documentation and Quick Start guide update.
   - Guided setup CLI/script.
   - QA pass, accessibility review (screen reader labels, contrast check).
   - User docs (Quick Start, troubleshooting, FAQ).

7. **Phase 6**: Performance & Web Optimizations
   - Use FlashList (Shopify) for mobile library virtualization; fallback to RecyclerListView if needed.
   - On web builds, leverage TanStack Virtual or a web-specific grid component.
   - Enforce backend pagination (per-page limits) and server-side filtering to keep payloads small.
   - Profile UI screens, add skeleton loaders and prefetching for smoother UX.
   - Consider offline read-only cache for mobile (persisted snapshot).
   - Add analytics dashboard (job durations, success rate).

## Notes
- Ensure resolver uses latest catalog (JSON or SQLite) and returns highest quality variant.
- Expose library counts via backend for dashboard stats.
- Consider plugin architecture for future content sources (beyond HDFilm/Dizibox).
- Keep CLI commands available for automation; UI calls the same endpoints.
- Add localization (TR/EN) and accessibility considerations from the start.
- Deployment docs should cover local (docker compose) and cloud (ECS/Kubernetes) scenarios.
- Define retention/backup for catalogs, STRM exports, and job logs (location, frequency, restore steps) to safeguard production data.
