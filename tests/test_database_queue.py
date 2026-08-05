from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from omni_healthcheck.database import (
    DatabaseMetadataStore,
    JobLeaseLostError,
    create_database_engine,
    queue_claim_statement,
)


def test_epas_engine_forces_iso_datestyle(monkeypatch) -> None:
    captured = {}

    def fake_create_engine(url, **options):
        captured["url"] = url
        captured["options"] = options
        return object()

    monkeypatch.setattr("omni_healthcheck.database.create_engine", fake_create_engine)
    engine = create_database_engine(
        "postgresql+psycopg://omnicheck_app@db/omnicheck_app"
    )

    assert engine is not None
    assert captured["options"]["connect_args"] == {"options": "-c DateStyle=ISO"}
from omni_healthcheck.job_store import JobStore
from omni_healthcheck.web import create_app
from omni_healthcheck.worker import run_once

from test_web import FIXTURE, ROOT, _config


def _database_store(tmp_path: Path) -> DatabaseMetadataStore:
    store = DatabaseMetadataStore(f"sqlite+pysqlite:///{tmp_path / 'metadata.sqlite'}")
    store.create_schema_for_test()
    return store


def _upload_fixture(client: TestClient, job_id: str) -> None:
    files = [
        (
            "files",
            (
                path.relative_to(FIXTURE / "input").as_posix(),
                path.read_bytes(),
                "application/octet-stream",
            ),
        )
        for path in sorted((FIXTURE / "input").rglob("*"))
        if path.is_file()
    ]
    response = client.post(f"/api/jobs/{job_id}/files", files=files)
    assert response.status_code == 201


def test_database_queue_claim_uses_skip_locked() -> None:
    sql = str(
        queue_claim_statement(datetime.now(UTC)).compile(
            dialect=postgresql.dialect()
        )
    )
    assert "FOR UPDATE SKIP LOCKED" in sql


def test_database_metadata_claim_retry_and_events(tmp_path: Path) -> None:
    metadata = _database_store(tmp_path)
    store = JobStore(tmp_path / "jobs", metadata_store=metadata)
    from omni_healthcheck.config import JobConfig

    job = store.create(JobConfig.model_validate(_config()))
    store.update(job["job_id"], input_files=1, status="queued")

    claimed = store.claim_next("worker-a")
    assert claimed is not None
    assert claimed["status"] == "running"
    assert claimed["attempts"] == 1
    assert store.claim_next("worker-b") is None

    retried = store.fail(
        job["job_id"],
        "worker-a",
        "temporary failure",
        retry_seconds=0,
    )
    assert retried["status"] == "queued"
    claimed_again = store.claim_next("worker-b")
    assert claimed_again is not None
    assert claimed_again["attempts"] == 2
    completed = store.succeed(job["job_id"], "worker-b")
    assert completed["status"] == "succeeded"

    event_types = [event["event_type"] for event in store.events(job["job_id"])]
    assert event_types == [
        "created",
        "status_changed",
        "claimed",
        "retry_scheduled",
        "claimed",
        "completed",
    ]


def test_database_backed_web_queues_for_external_worker(tmp_path: Path) -> None:
    metadata = _database_store(tmp_path)
    app = create_app(
        data_root=tmp_path / "jobs",
        rules_path=ROOT / "config/rules.default.yaml",
        metadata_store=metadata,
    )
    client = TestClient(app)
    health = client.get("/api/health").json()
    assert health["metadata"] == "database"
    assert health["worker"] == "external"

    job_id = client.post("/api/jobs", json=_config()).json()["job_id"]
    _upload_fixture(client, job_id)
    queued = client.post(f"/api/jobs/{job_id}/run")
    assert queued.status_code == 202
    queued_job = client.get(f"/api/jobs/{job_id}").json()
    assert queued_job["status"] == "queued"
    assert queued_job["outputs"] == []
    assert client.get(f"/api/jobs/{job_id}/outputs").status_code == 409

    processed = run_once(
        app.state.job_store,
        "test-worker",
        ROOT / "config/rules.default.yaml",
        retry_seconds=0,
    )
    assert processed is True
    completed = client.get(f"/api/jobs/{job_id}").json()
    assert completed["status"] == "succeeded"
    assert "qa-result.json" in {item["name"] for item in completed["outputs"]}
    assert client.get(f"/api/jobs/{job_id}/events").status_code == 200


def test_database_queue_stops_after_max_attempts(tmp_path: Path) -> None:
    metadata = _database_store(tmp_path)
    store = JobStore(tmp_path / "jobs", metadata_store=metadata)
    from omni_healthcheck.config import JobConfig

    job_id = store.create(JobConfig.model_validate(_config()))["job_id"]
    store.update(job_id, input_files=1, status="queued")
    for attempt in range(1, 4):
        claimed = store.claim_next("failing-worker")
        assert claimed is not None
        assert claimed["attempts"] == attempt
        result = store.fail(
            job_id,
            "failing-worker",
            f"failure {attempt}",
            retry_seconds=0,
        )

    assert result["status"] == "failed"
    assert store.claim_next("another-worker") is None


def test_database_queue_enforces_worker_lease(tmp_path: Path) -> None:
    metadata = _database_store(tmp_path)
    store = JobStore(tmp_path / "jobs", metadata_store=metadata)
    from omni_healthcheck.config import JobConfig

    job_id = store.create(JobConfig.model_validate(_config()))["job_id"]
    store.update(job_id, input_files=1, status="queued")
    assert store.claim_next("worker-a") is not None
    assert store.heartbeat(job_id, "worker-a") is True
    assert store.heartbeat(job_id, "worker-b") is False

    metadata.update(job_id, claimed_by="worker-b", status="running")
    with pytest.raises(JobLeaseLostError):
        store.succeed(job_id, "worker-a")


def test_database_queue_recovers_stale_worker(tmp_path: Path) -> None:
    metadata = _database_store(tmp_path)
    store = JobStore(tmp_path / "jobs", metadata_store=metadata)
    from omni_healthcheck.config import JobConfig

    job_id = store.create(JobConfig.model_validate(_config()))["job_id"]
    stale_time = datetime.now(UTC) - timedelta(hours=2)
    metadata.update(
        job_id,
        status="running",
        attempts=1,
        claimed_by="dead-worker",
        claimed_at=stale_time,
    )
    assert metadata.recover_stale(3600) == 1
    assert store.get(job_id)["status"] == "queued"


def test_database_health_fails_closed(tmp_path: Path) -> None:
    class UnavailableMetadata:
        def ping(self) -> None:
            raise ConnectionError("database unavailable")

    client = TestClient(
        create_app(
            data_root=tmp_path / "jobs",
            metadata_store=UnavailableMetadata(),
        )
    )
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json()["detail"] == "metadata database unavailable"
