from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from omni_healthcheck.application_data import ApplicationDataStore
from omni_healthcheck.artifact_lifecycle import ArtifactRegistry
from omni_healthcheck.cli import run_generate
from omni_healthcheck.config import JobConfig
from omni_healthcheck.database import DatabaseMetadataStore
from omni_healthcheck.job_store import JobStore

from test_web import FIXTURE, ROOT, _config


def foundation(tmp_path: Path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'm96.sqlite'}"
    application = ApplicationDataStore(database_url)
    application.create_schema_for_test()
    jobs = JobStore(tmp_path / "jobs", metadata_store=DatabaseMetadataStore(database_url))
    customer = application.create_customer(tenant_key="artifact-customer", name="Artifact")
    system = application.create_system(
        customer["customer_id"], system_key="artifact-system", name="Artifact System",
        environment="test", product="EPAS",
    )
    job = jobs.create(JobConfig.model_validate(_config()))
    application.associate_job(customer["customer_id"], system["system_id"], job["job_id"])
    return database_url, application, jobs, customer, system, job


def test_registers_output_versions_relations_and_events_idempotently(tmp_path: Path) -> None:
    database_url, application, jobs, customer, system, job = foundation(tmp_path)
    output = jobs.paths(job["job_id"])["output"]
    assert run_generate(
        FIXTURE / "job.yaml", FIXTURE / "input", output,
        ROOT / "config/rules.default.yaml",
    ) == 0
    registry = ArtifactRegistry(database_url)
    arguments = dict(
        job_id=job["job_id"], customer_id=customer["customer_id"],
        system_id=system["system_id"], output_dir=output,
        data_root=tmp_path, retention_days=30,
    )

    first = registry.register_outputs(**arguments)
    second = registry.register_outputs(**arguments)

    assert len(first) == 12
    assert {item["artifact_id"] for item in second} == {
        item["artifact_id"] for item in first
    }
    assert {item["artifact_version"] for item in first} == {1}
    assert len(application.list_artifacts(
        customer["customer_id"], system["system_id"], job["job_id"]
    )) == 12
    assert len(registry.list_relations(customer["customer_id"], job["job_id"])) == 3
    assert all(
        registry.list_events(customer["customer_id"], item["artifact_id"])[0]["event_type"]
        == "registered"
        for item in first
    )


def test_changed_output_creates_next_artifact_version(tmp_path: Path) -> None:
    database_url, application, jobs, customer, system, job = foundation(tmp_path)
    output = jobs.paths(job["job_id"])["output"]
    output.mkdir(parents=True, exist_ok=True)
    target = output / "normalized.json"
    target.write_text('{"version": 1}\n', encoding="utf-8")
    registry = ArtifactRegistry(database_url)
    arguments = dict(
        job_id=job["job_id"], customer_id=customer["customer_id"],
        system_id=system["system_id"], output_dir=output, data_root=tmp_path,
    )
    registry.register_outputs(**arguments)
    target.write_text('{"version": 2}\n', encoding="utf-8")
    registry.register_outputs(**arguments)

    artifacts = application.list_artifacts(
        customer["customer_id"], system["system_id"], job["job_id"]
    )
    assert [item["artifact_version"] for item in artifacts] == [1, 2]
    assert artifacts[0]["sha256"] != artifacts[1]["sha256"]
    relations = registry.list_relations(customer["customer_id"], job["job_id"])
    assert len(relations) == 1
    assert relations[0]["relation_type"] == "supersedes"


def test_archive_is_dry_run_by_default_and_preserves_source(tmp_path: Path) -> None:
    database_url, application, _, customer, system, job = foundation(tmp_path)
    active_root = tmp_path / "active"
    archive_root = tmp_path / "archive"
    source = active_root / "jobs" / job["job_id"] / "output" / "report.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"validated report")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    artifact = application.register_artifact(
        customer["customer_id"], system["system_id"], job["job_id"],
        artifact_type="report-pdf",
        storage_key=source.relative_to(active_root).as_posix(),
        sha256=digest, file_size=source.stat().st_size, media_type="application/pdf",
        retention_until=datetime.now(UTC) - timedelta(days=1),
    )
    registry = ArtifactRegistry(database_url)

    preview = registry.archive_due(active_root=active_root, archive_root=archive_root)
    assert preview == [{
        "artifact_id": artifact["artifact_id"], "source": str(source.resolve()),
        "archive_key": (
            f"artifacts/{customer['customer_id']}/{job['job_id']}/"
            f"{artifact['artifact_id']}/report.pdf"
        ), "applied": False,
    }]
    assert not archive_root.exists()

    applied = registry.archive_due(
        active_root=active_root, archive_root=archive_root, apply=True
    )
    assert applied[0]["applied"] is True
    assert source.is_file()
    archived = application.list_artifacts(
        customer["customer_id"], system["system_id"], job["job_id"]
    )[0]
    assert archived["archive_status"] == "archived"
    assert archived["storage_root_version"] == "archive-v1"
    archived_path = archive_root / archived["storage_key"]
    assert archived_path.read_bytes() == source.read_bytes()
    assert [event["event_type"] for event in registry.list_events(
        customer["customer_id"], artifact["artifact_id"]
    )] == ["archived"]

    pending = registry.request_delete(
        customer["customer_id"], artifact["artifact_id"], reason="retention approved"
    )
    assert pending["archive_status"] == "pending_delete"
    restored = registry.cancel_delete(
        customer["customer_id"], artifact["artifact_id"], reason="legal hold"
    )
    assert restored["archive_status"] == "archived"
    assert [event["event_type"] for event in registry.list_events(
        customer["customer_id"], artifact["artifact_id"]
    )] == ["archived", "delete_requested", "delete_cancelled"]


def test_delete_request_requires_archived_artifact(tmp_path: Path) -> None:
    database_url, application, _, customer, system, job = foundation(tmp_path)
    artifact = application.register_artifact(
        customer["customer_id"], system["system_id"], job["job_id"],
        artifact_type="qa-json", storage_key="jobs/example/output/qa-result.json",
        sha256="f" * 64, file_size=1, media_type="application/json",
    )
    registry = ArtifactRegistry(database_url)
    try:
        registry.request_delete(
            customer["customer_id"], artifact["artifact_id"], reason="too early"
        )
    except ValueError as exc:
        assert "only archived" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("active artifact unexpectedly entered pending_delete")
