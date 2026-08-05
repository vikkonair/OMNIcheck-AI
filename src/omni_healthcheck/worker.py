"""Standalone durable worker for database-backed M9.3 jobs."""

from __future__ import annotations

import os
import signal
import socket
import threading
import time
from pathlib import Path

from omni_healthcheck.cli import run_generate
from omni_healthcheck.database import DatabaseMetadataStore
from omni_healthcheck.job_store import JobStore


def run_once(
    store: JobStore,
    worker_id: str,
    rules_path: Path,
    *,
    retry_seconds: int,
    heartbeat_seconds: float = 30,
) -> bool:
    job = store.claim_next(worker_id)
    if job is None:
        return False
    job_id = job["job_id"]
    heartbeat_stop = threading.Event()

    def heartbeat() -> None:
        while not heartbeat_stop.wait(heartbeat_seconds):
            if not store.heartbeat(job_id, worker_id):
                return

    heartbeat_thread = None
    if heartbeat_seconds > 0:
        heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
        heartbeat_thread.start()
    try:
        paths = store.paths(job_id)
        run_generate(paths["job"], paths["input"], paths["output"], rules_path)
    except Exception as exc:
        store.fail(
            job_id,
            worker_id,
            str(exc),
            retry_seconds=retry_seconds,
        )
    else:
        store.succeed(job_id, worker_id)
    finally:
        heartbeat_stop.set()
        if heartbeat_thread is not None:
            heartbeat_thread.join(timeout=max(heartbeat_seconds, 1))
    return True


def main() -> None:
    database_url = os.environ.get("OMNICHECK_DATABASE_URL")
    if not database_url:
        raise SystemExit("OMNICHECK_DATABASE_URL is required for the worker")

    data_root = Path(os.environ.get("OMNICHECK_DATA_ROOT", "/data/omnicheck/jobs"))
    rules_path = Path(
        os.environ.get("OMNICHECK_RULES_PATH", "config/rules.default.yaml")
    ).resolve()
    poll_seconds = float(os.environ.get("OMNICHECK_WORKER_POLL_SECONDS", "2"))
    retry_seconds = int(os.environ.get("OMNICHECK_WORKER_RETRY_SECONDS", "60"))
    heartbeat_seconds = float(
        os.environ.get("OMNICHECK_WORKER_HEARTBEAT_SECONDS", "30")
    )
    stale_seconds = int(os.environ.get("OMNICHECK_WORKER_STALE_SECONDS", "3600"))
    worker_id = os.environ.get(
        "OMNICHECK_WORKER_ID",
        f"{socket.gethostname()}-{os.getpid()}",
    )

    metadata_store = DatabaseMetadataStore(database_url)
    store = JobStore(data_root, metadata_store=metadata_store)
    metadata_store.recover_stale(stale_seconds)

    stopping = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    while not stopping:
        processed = run_once(
            store,
            worker_id,
            rules_path,
            retry_seconds=retry_seconds,
            heartbeat_seconds=heartbeat_seconds,
        )
        if not processed:
            time.sleep(poll_seconds)
