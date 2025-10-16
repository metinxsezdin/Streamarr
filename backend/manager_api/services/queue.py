"""Redis-backed job queue integration for the manager service."""
from __future__ import annotations

from typing import Any

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue

try:  # pragma: no cover - optional dependency for test environments
    import fakeredis
except ModuleNotFoundError:  # pragma: no cover - runtime path without fakeredis
    fakeredis = None  # type: ignore[assignment]

from ..schemas import JobLogCreate, JobModel
from ..settings import ManagerSettings
from ..stores.job_log_store import JobLogStore
from ..stores.job_store import JobStore
from .tasks import execute_manager_job


class JobQueueError(RuntimeError):
    """Raised when the queue cannot accept a job."""


class JobQueueService:
    """Encapsulates the Redis queue connection and enqueue workflow."""

    def __init__(self, settings: ManagerSettings) -> None:
        self._settings = settings
        self._connection = self._create_connection(settings)
        self._queue = Queue(settings.redis_queue_name, connection=self._connection)

    @staticmethod
    def _create_connection(settings: ManagerSettings) -> Redis:
        """Instantiate a Redis connection, supporting fakeredis for tests."""

        url = settings.redis_url
        if url.startswith("fakeredis://"):
            if fakeredis is None:  # pragma: no cover - safety branch
                msg = "fakeredis is required for fakeredis:// URLs"
                raise JobQueueError(msg)
            return fakeredis.FakeRedis()  # type: ignore[return-value]
        return Redis.from_url(url)

    @property
    def queue(self) -> Queue:
        """Expose the underlying RQ queue for workers and diagnostics."""

        return self._queue

    @property
    def connection(self) -> Redis:
        """Return the Redis connection used by the queue."""

        return self._connection

    def ping(self) -> bool:
        """Check whether the queue backend is reachable."""

        try:
            return bool(self._connection.ping())
        except RedisError:
            return False

    def enqueue(
        self,
        job_store: JobStore,
        log_store: JobLogStore,
        job_type: str,
        payload: dict[str, Any] | None = None,
    ) -> JobModel:
        """Persist a job and enqueue it for asynchronous execution."""

        job = job_store.enqueue(job_type, payload)
        log_store.append(
            job.id,
            JobLogCreate(
                level="info",
                message=f"Job {job_type} enqueued",
                context={"payload": payload} if payload else None,
            ),
        )

        try:
            self._queue.enqueue(
                execute_manager_job,
                job_id=job.id,
                kwargs={
                    "job_id": job.id,
                    "job_type": job_type,
                    "payload": payload,
                    "settings": self._settings.model_dump(),
                    "worker_name": self._settings.queue_worker_name,
                },
            )
        except RedisError as exc:  # pragma: no cover - failure path
            log_store.append(
                job.id,
                JobLogCreate(
                    level="error",
                    message="Failed to enqueue job",
                    context={"error": str(exc)},
                ),
            )
            job_store.mark_failed(job.id, error_message="queue_unavailable", progress=0.0)
            raise JobQueueError("Unable to enqueue job") from exc

        return job

