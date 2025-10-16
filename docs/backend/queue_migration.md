# Queue Migration Guide (Phase 1.5)

The manager backend now uses a Redis-backed RQ queue for job orchestration. This
guide summarizes the steps required to migrate from the previous synchronous
workflow.

## Prerequisites

1. Ensure Redis 7+ is available. For local development, `docker-compose up redis`
   starts the bundled service that listens on `localhost:6379`.
2. Install the new Python dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Configuration Updates

The manager automatically reads queue settings from environment variables. The
defaults point to `redis://localhost:6379/0` and enqueue jobs on the
`streamarr-manager` queue using the worker name `manager-worker`. Override these
values with the following variables when necessary:

```
STREAMARR_MANAGER_REDIS_URL=redis://<host>:<port>/<db>
STREAMARR_MANAGER_REDIS_QUEUE_NAME=<queue-name>
STREAMARR_MANAGER_QUEUE_WORKER_NAME=<worker-id>
```

## Running the Worker

Launch the FastAPI app as before (`make dev`) and start the background worker in
a separate terminal using:

```bash
cd backend
make worker
```

The worker connects to Redis, pulls jobs from the configured queue, and updates
job status/log records in SQLite.

## CLI and API Behaviour Changes

* `POST /jobs/run` and `streamarr-manager jobs run` now return immediately with a
  `queued` job. Use the new `--wait` flag on the CLI to poll for completion when
  a worker is running.
* `/health` responses include queue connectivity information, allowing monitors
  to detect Redis outages.
* Job logs contain an additional entry (`Executing <job_type> job`) emitted by
  the worker during processing.

## Observability

* The Manager API exposes `/jobs/metrics` to report aggregated job counts,
  average durations, and the current Redis queue depth. Use this endpoint (or
  the `streamarr-manager jobs metrics` CLI command) to confirm workers are
  draining the queue after migration.

## Troubleshooting

* If `/health` reports `queue_unreachable`, verify that Redis is running and the
  `STREAMARR_MANAGER_REDIS_URL` matches the active instance.
* Jobs stuck in `queued` status indicate the worker is offline or cannot reach
  Redis. Restart `make worker` and inspect worker logs for connection issues.

