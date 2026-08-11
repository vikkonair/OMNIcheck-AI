"""Standalone durable worker for database-backed M9.3 jobs."""

from __future__ import annotations

import os
import json
import signal
import socket
import threading
import time
from pathlib import Path

from omni_healthcheck.artifact_lifecycle import ArtifactRegistry
from omni_healthcheck.ai_batch import AIDraftBatchStore
from omni_healthcheck.ai_gateway import AIGatewaySettings, OllamaGateway
from omni_healthcheck.ai_persistence import AIGatewayAuditStore
from omni_healthcheck.cli import run_generate
from omni_healthcheck.database import DatabaseMetadataStore
from omni_healthcheck.job_store import JobStore
from omni_healthcheck.pipeline_persistence import PipelineResultStore
from omni_healthcheck.section_persistence import SectionWorkflowStore
from omni_healthcheck.section_workflow import SectionWorkflowDocument


def run_ai_batch_once(
    batch_store: AIDraftBatchStore,
    section_store: SectionWorkflowStore,
    gateway: OllamaGateway,
    worker_id: str,
    *,
    min_interval_seconds: float = 1.0,
) -> bool:
    """Process one durable batch sequentially; failures retain deterministic text."""

    batch = batch_store.claim_next(worker_id)
    if batch is None:
        return False
    for index, queued in enumerate(batch["items"]):
        if queued["status"] in {"ai_drafted", "fallback", "conflict"}:
            continue
        try:
            item = section_store.get_item(batch["job_id"], queued["item_id"])
            if item.revision != queued["expected_revision"]:
                batch_store.finish_item(
                    batch["batch_id"], queued["batch_item_id"], status="conflict",
                    error=f"revision changed from {queued['expected_revision']} to {item.revision}",
                )
                continue
            result = gateway.generate(
                job_id=batch["job_id"], item_id=queued["item_id"], item=item,
                requested_by=batch["actor"],
            )
            if result.draft is None:
                batch_store.finish_item(
                    batch["batch_id"], queued["batch_item_id"], status="fallback",
                    request_id=result.request_id, error=result.error,
                )
            else:
                try:
                    section_store.transition(
                        batch["job_id"], queued["item_id"],
                        expected_revision=queued["expected_revision"], action="ai_drafted",
                        actor=f"ai:ollama:{gateway.settings.model}",
                        observation=result.draft.observation,
                        recommendation=result.draft.recommendation,
                    )
                except Exception as exc:
                    if result.request_id:
                        gateway.discard_stale(result.request_id)
                    batch_store.finish_item(
                        batch["batch_id"], queued["batch_item_id"], status="conflict",
                        request_id=result.request_id, error=str(exc),
                    )
                else:
                    batch_store.finish_item(
                        batch["batch_id"], queued["batch_item_id"], status="ai_drafted",
                        request_id=result.request_id,
                    )
        except Exception as exc:
            batch_store.finish_item(
                batch["batch_id"], queued["batch_item_id"], status="fallback",
                error=f"{type(exc).__name__}: {exc}",
            )
        if index + 1 < len(batch["items"]) and min_interval_seconds > 0:
            time.sleep(min(min_interval_seconds, 30.0))
    batch_store.finalize(batch["job_id"], batch["batch_id"])
    return True


def run_once(
    store: JobStore,
    worker_id: str,
    rules_path: Path,
    *,
    retry_seconds: int,
    heartbeat_seconds: float = 30,
    persist_results: bool = True,
    register_artifacts: bool = True,
    artifact_retention_days: int = 365,
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
        customer_id = job.get("customer_id")
        system_id = job.get("system_id")
        if (persist_results or register_artifacts) and (customer_id or system_id):
            if not customer_id or not system_id:
                raise RuntimeError("Pipeline results require complete customer/system scope")
            if store.metadata_store is None:
                raise RuntimeError("Pipeline results require database metadata")
        if persist_results and customer_id and system_id:
            PipelineResultStore(engine=store.metadata_store.engine).persist(
                job_id=job_id,
                customer_id=str(customer_id),
                system_id=str(system_id),
                output_dir=paths["output"],
            )
        if persist_results:
            if store.metadata_store is None:
                raise RuntimeError("Section Workflow persistence requires database metadata")
            workflow = SectionWorkflowDocument.model_validate(
                json.loads((paths["output"] / "section-workflow.json").read_text(encoding="utf-8"))
            )
            SectionWorkflowStore(engine=store.metadata_store.engine).persist_baseline(
                job_id, workflow
            )
        if register_artifacts and customer_id and system_id:
            ArtifactRegistry(engine=store.metadata_store.engine).register_outputs(
                job_id=job_id,
                customer_id=str(customer_id),
                system_id=str(system_id),
                output_dir=paths["output"],
                data_root=store.root.parent,
                retention_days=artifact_retention_days,
            )
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
    persist_results = os.environ.get("OMNICHECK_PERSIST_RESULTS", "true").lower() not in {
        "0", "false", "no",
    }
    register_artifacts = os.environ.get(
        "OMNICHECK_REGISTER_ARTIFACTS", "true"
    ).lower() not in {"0", "false", "no"}
    artifact_retention_days = int(
        os.environ.get("OMNICHECK_ARTIFACT_RETENTION_DAYS", "365")
    )
    worker_id = os.environ.get(
        "OMNICHECK_WORKER_ID",
        f"{socket.gethostname()}-{os.getpid()}",
    )

    metadata_store = DatabaseMetadataStore(database_url)
    store = JobStore(data_root, metadata_store=metadata_store)
    metadata_store.recover_stale(stale_seconds)
    ai_settings = AIGatewaySettings.from_env()
    ai_gateway = OllamaGateway(
        ai_settings, AIGatewayAuditStore(engine=metadata_store.engine)
    )
    ai_batches = AIDraftBatchStore(
        engine=metadata_store.engine,
        max_items=int(os.environ.get("OMNICHECK_AI_BATCH_MAX_ITEMS", "5")),
    )
    ai_batches.recover_stale(stale_seconds)
    section_store = SectionWorkflowStore(engine=metadata_store.engine)
    ai_min_interval = float(
        os.environ.get("OMNICHECK_AI_MIN_INTERVAL_SECONDS", "1")
    )

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
            persist_results=persist_results,
            register_artifacts=register_artifacts,
            artifact_retention_days=artifact_retention_days,
        )
        if not processed:
            processed = run_ai_batch_once(
                ai_batches, section_store, ai_gateway, worker_id,
                min_interval_seconds=ai_min_interval,
            )
        if not processed:
            time.sleep(poll_seconds)
