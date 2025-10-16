#!/usr/bin/env python3
"""Convenience runner for the manager API, Redis queue, and worker."""
from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
import redis

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REDIS_URL = "redis://localhost:6379/0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Start the Streamarr manager API and background worker with a single command. "
            "Redis is automatically launched via docker-compose unless --no-start-redis is provided."
        )
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host interface for the FastAPI server")
    parser.add_argument("--port", type=int, default=8000, help="Port for the FastAPI server")
    parser.add_argument(
        "--redis-url",
        default=DEFAULT_REDIS_URL,
        help="Redis connection URL used by the API and worker",
    )
    parser.add_argument(
        "--no-reload",
        dest="reload",
        action="store_false",
        help="Disable FastAPI auto-reload (enabled by default)",
    )
    parser.set_defaults(reload=True)
    parser.add_argument(
        "--no-start-redis",
        dest="start_redis",
        action="store_false",
        help="Skip docker-compose redis startup",
    )
    parser.set_defaults(start_redis=True)
    parser.add_argument(
        "--compose-file",
        type=Path,
        default=PROJECT_ROOT / "docker-compose.yml",
        help="docker-compose file used when launching Redis",
    )
    parser.add_argument(
        "--redis-service",
        default="redis",
        help="docker-compose service name for Redis",
    )
    return parser.parse_args()


def log(message: str) -> None:
    print(f"[manager-stack] {message}")


def ensure_redis(redis_url: str, compose_file: Path, service: str, start_redis: bool) -> None:
    if start_redis:
        docker_exe = "docker"
        if shutil.which(docker_exe) is None:
            log("Docker not found; skipping docker-compose Redis startup.")
        else:
            compose_cmd = [docker_exe, "compose"]
            if compose_file.exists():
                compose_cmd.extend(["-f", str(compose_file)])
            compose_cmd.extend(["up", "-d", service])
            log("Starting Redis via docker compose...")
            result = subprocess.run(compose_cmd, check=False, cwd=str(PROJECT_ROOT))
            if result.returncode != 0:
                log(
                    "docker compose exited with a non-zero status; continuing in case Redis is already running."
                )

    client = redis.Redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
    for attempt in range(10):
        try:
            client.ping()
            log("Redis connection established.")
            return
        except redis.exceptions.RedisError as exc:  # pragma: no cover - network dependent
            log(f"Waiting for Redis ({exc!s})...")
            time.sleep(0.5 * (attempt + 1))
    raise SystemExit("Redis is not available. Check the URL or use --no-start-redis if managing it manually.")


def build_api_command(host: str, port: int, reload: bool) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.manager_api.app:create_app",
        "--factory",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if reload:
        command.append("--reload")
    return command


def build_worker_command() -> list[str]:
    return [sys.executable, "-m", "backend.manager_worker"]


def launch_processes(api_cmd: list[str], worker_cmd: list[str], env: dict[str, str]) -> list[subprocess.Popen]:
    processes: list[subprocess.Popen] = []
    log("Starting FastAPI server...")
    processes.append(
        subprocess.Popen(api_cmd, cwd=str(PROJECT_ROOT), env=env)
    )
    log("Starting background worker...")
    processes.append(
        subprocess.Popen(worker_cmd, cwd=str(PROJECT_ROOT), env=env)
    )
    return processes


def forward_signals(processes: list[subprocess.Popen]) -> None:
    def _handler(signum: int, _frame) -> None:
        log(f"Received signal {signum}; shutting down...")
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
        for proc in processes:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)



def monitor(processes: list[subprocess.Popen]) -> None:
    try:
        while True:
            for proc in processes:
                returncode = proc.poll()
                if returncode is not None:
                    raise SystemExit(returncode)
            time.sleep(0.5)
    except KeyboardInterrupt:
        log("Interrupted by user; stopping processes...")
    finally:
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
        for proc in processes:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


def main() -> None:
    args = parse_args()

    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH", "")
    if pythonpath:
        env["PYTHONPATH"] = f"{PROJECT_ROOT}{os.pathsep}{pythonpath}"
    else:
        env["PYTHONPATH"] = str(PROJECT_ROOT)
    env.setdefault("STREAMARR_MANAGER_REDIS_URL", args.redis_url)

    ensure_redis(args.redis_url, args.compose_file, args.redis_service, args.start_redis)

    api_cmd = build_api_command(args.host, args.port, args.reload)
    worker_cmd = build_worker_command()

    processes = launch_processes(api_cmd, worker_cmd, env)
    forward_signals(processes)
    log(
        "Manager stack ready. FastAPI is available at "
        f"http://{args.host}:{args.port} and the worker is attached to {args.redis_url}."
    )
    monitor(processes)


if __name__ == "__main__":  # pragma: no cover - manual entrypoint
    main()
