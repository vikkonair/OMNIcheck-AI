from __future__ import annotations

from pathlib import Path

import pytest

from omni_healthcheck.application_data import ApplicationDataStore
from omni_healthcheck.artifact_lifecycle import ArtifactRegistry
from omni_healthcheck.cli import run_generate
from omni_healthcheck.config import JobConfig
from omni_healthcheck.database import DatabaseMetadataStore
from omni_healthcheck.job_store import JobStore
from omni_healthcheck.pipeline_persistence import PipelineResultStore
from omni_healthcheck.worker import run_once

from test_web import FIXTURE, ROOT, _config


def foundation(tmp_path: Path):
    url = f"sqlite+pysqlite:///{tmp_path / 'm95.sqlite'}"
    app = ApplicationDataStore(url)
    app.create_schema_for_test()
    jobs = JobStore(tmp_path / "jobs", metadata_store=DatabaseMetadataStore(url))
    customer = app.create_customer(tenant_key="golden-customer", name="Golden Customer")
    system = app.create_system(
        customer["customer_id"], system_key="golden-v4", name="Golden V4",
        environment="test", product="EPAS",
    )
    for node in JobConfig.model_validate(_config()).nodes:
        app.create_node(
            customer["customer_id"], system["system_id"],
            hostname=node.hostname, role=node.role, product="EPAS",
            attributes={"services": node.services},
        )
    job = jobs.create(JobConfig.model_validate(_config()))
    app.associate_job(customer["customer_id"], system["system_id"], job["job_id"])
    return url, app, jobs, customer, system, job


def generate(output: Path) -> None:
    assert run_generate(
        FIXTURE / "job.yaml", FIXTURE / "input", output,
        ROOT / "config/rules.default.yaml",
    ) == 0


def test_pipeline_snapshot_is_queryable_and_idempotent(tmp_path: Path) -> None:
    url, _, _, customer, system, job = foundation(tmp_path)
    output = tmp_path / "output"
    generate(output)
    store = PipelineResultStore(url)

    first = store.persist(
        job_id=job["job_id"], customer_id=customer["customer_id"],
        system_id=system["system_id"], output_dir=output,
    )
    second = store.persist(
        job_id=job["job_id"], customer_id=customer["customer_id"],
        system_id=system["system_id"], output_dir=output,
    )

    assert first["created"] is True
    assert second["created"] is False
    assert second["snapshot_id"] == first["snapshot_id"]
    assert len(first["canonical_sha256"]) == 64
    counts = store.counts(customer["customer_id"], first["snapshot_id"])
    assert counts["scope_decisions"] == 3
    assert counts["normalized_checks"] > 0
    assert counts["normalized_unparsed"] == 0
    assert counts["configuration_comparisons"] == 3
    assert counts["pipeline_assessments"] == 3
    assert counts["coverage_items"] == 40
    assert counts["quality_results"] == 2
    with pytest.raises(KeyError):
        store.get("another-tenant", first["snapshot_id"])


def test_persistence_requires_complete_output_set(tmp_path: Path) -> None:
    url, _, _, customer, system, job = foundation(tmp_path)
    with pytest.raises(FileNotFoundError, match="missing pipeline outputs"):
        PipelineResultStore(url).persist(
            job_id=job["job_id"], customer_id=customer["customer_id"],
            system_id=system["system_id"], output_dir=tmp_path / "empty",
        )


def test_worker_persists_scoped_job_before_success(tmp_path: Path) -> None:
    url, app, jobs, customer, system, job = foundation(tmp_path)
    paths = jobs.paths(job["job_id"])
    for source in sorted((FIXTURE / "input").rglob("*")):
        if source.is_file():
            destination = paths["input"] / source.relative_to(FIXTURE / "input")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
    jobs.update(job["job_id"], input_files=3, status="queued")

    assert run_once(
        jobs, "m95-worker", ROOT / "config/rules.default.yaml",
        retry_seconds=0, heartbeat_seconds=0,
    ) is True
    assert jobs.get(job["job_id"])["status"] == "succeeded"
    snapshots = PipelineResultStore(url)
    with snapshots.engine.connect() as connection:
        from omni_healthcheck.pipeline_persistence import pipeline_snapshots
        row = connection.execute(pipeline_snapshots.select()).mappings().one()
    assert row["customer_id"] == customer["customer_id"]
    assert row["system_id"] == system["system_id"]
    assert len(app.list_artifacts(
        customer["customer_id"], system["system_id"], job["job_id"]
    )) == 12
    assert len(ArtifactRegistry(url).list_relations(
        customer["customer_id"], job["job_id"]
    )) == 3


def test_worker_auto_queues_all_visible_sections_after_baseline(tmp_path: Path) -> None:
    _, _, jobs, _, _, job = foundation(tmp_path)
    paths = jobs.paths(job["job_id"])
    for source in sorted((FIXTURE / "input").rglob("*")):
        if source.is_file():
            destination = paths["input"] / source.relative_to(FIXTURE / "input")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
    jobs.update(job["job_id"], input_files=3, status="queued")

    class BatchRecorder:
        calls = []

        def create_all_generated(self, job_id: str, actor: str):
            self.calls.append((job_id, actor))
            return []

    batches = BatchRecorder()
    assert run_once(
        jobs, "m143-worker", ROOT / "config/rules.default.yaml",
        retry_seconds=0, heartbeat_seconds=0,
        ai_batch_store=batches, auto_ai_draft_all=True,
    ) is True
    assert batches.calls == [(job["job_id"], "system:auto-ai")]


def test_legacy_unscoped_worker_remains_compatible(tmp_path: Path) -> None:
    url = f"sqlite+pysqlite:///{tmp_path / 'legacy.sqlite'}"
    metadata = DatabaseMetadataStore(url)
    metadata.create_schema_for_test()
    jobs = JobStore(tmp_path / "jobs", metadata_store=metadata)
    job = jobs.create(JobConfig.model_validate(_config()))
    paths = jobs.paths(job["job_id"])
    for source in sorted((FIXTURE / "input").rglob("*")):
        if source.is_file():
            destination = paths["input"] / source.relative_to(FIXTURE / "input")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
    jobs.update(job["job_id"], input_files=3, status="queued")

    run_once(jobs, "legacy-worker", ROOT / "config/rules.default.yaml", retry_seconds=0)
    assert jobs.get(job["job_id"])["status"] == "succeeded"


def test_persistence_failure_prevents_success(tmp_path: Path, monkeypatch) -> None:
    _, _, jobs, _, _, job = foundation(tmp_path)
    paths = jobs.paths(job["job_id"])
    for source in sorted((FIXTURE / "input").rglob("*")):
        if source.is_file():
            destination = paths["input"] / source.relative_to(FIXTURE / "input")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
    jobs.update(job["job_id"], input_files=3, status="queued")

    def fail(*args, **kwargs):
        raise RuntimeError("persistence unavailable")

    monkeypatch.setattr("omni_healthcheck.worker.PipelineResultStore.persist", fail)
    run_once(
        jobs, "failing-persistence-worker", ROOT / "config/rules.default.yaml",
        retry_seconds=0, heartbeat_seconds=0,
    )
    result = jobs.get(job["job_id"])
    assert result["status"] == "queued"
    assert "persistence unavailable" in result["error"]
