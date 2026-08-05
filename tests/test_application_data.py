from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from omni_healthcheck.application_data import ApplicationDataStore
from omni_healthcheck.config import JobConfig
from omni_healthcheck.database import DatabaseMetadataStore
from omni_healthcheck.job_store import JobStore

from test_web import _config


def _stores(tmp_path: Path) -> tuple[ApplicationDataStore, JobStore]:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'application.sqlite'}"
    application = ApplicationDataStore(database_url)
    application.create_schema_for_test()
    metadata = DatabaseMetadataStore(database_url)
    jobs = JobStore(tmp_path / "jobs", metadata_store=metadata)
    return application, jobs


def _foundation(tmp_path: Path):
    application, jobs = _stores(tmp_path)
    customer = application.create_customer(tenant_key="customer-a", name="Customer A")
    system = application.create_system(
        customer["customer_id"],
        system_key="production-db",
        name="Production DB",
        environment="production",
        product="EPAS",
    )
    primary = application.create_node(
        customer["customer_id"],
        system["system_id"],
        hostname="db-primary",
        role="Primary",
        product="EPAS",
    )
    standby = application.create_node(
        customer["customer_id"],
        system["system_id"],
        hostname="db-standby",
        role="Standby",
        product="EPAS",
    )
    job = jobs.create(JobConfig.model_validate(_config()))
    application.associate_job(customer["customer_id"], system["system_id"], job["job_id"])
    return application, jobs, customer, system, primary, standby, job


def test_m9_4_schema_contains_tenant_scoped_foundation_tables(tmp_path: Path) -> None:
    application, _ = _stores(tmp_path)
    inspector = inspect(application.engine)
    assert {
        "customers",
        "systems",
        "nodes",
        "topology_relations",
        "evidence_files",
        "artifacts",
        "jobs",
        "job_events",
    } <= set(inspector.get_table_names())
    job_columns = {column["name"] for column in inspector.get_columns("jobs")}
    assert {"customer_id", "system_id"} <= job_columns


def test_foundation_registers_topology_evidence_and_artifacts(tmp_path: Path) -> None:
    application, _, customer, system, primary, standby, job = _foundation(tmp_path)
    relation = application.create_topology_relation(
        customer["customer_id"],
        system["system_id"],
        source_node_id=primary["node_id"],
        target_node_id=standby["node_id"],
        relation_type="streams_to",
        evidence={"source": "confirmed configuration"},
    )
    evidence = application.register_evidence(
        customer["customer_id"],
        system["system_id"],
        job["job_id"],
        node_id=primary["node_id"],
        category="database",
        storage_key=f"jobs/{job['job_id']}/input/db/check.txt",
        sha256="a" * 64,
        file_size=123,
        media_type="text/plain",
    )
    artifact = application.register_artifact(
        customer["customer_id"],
        system["system_id"],
        job["job_id"],
        artifact_type="canonical-json",
        storage_key=f"jobs/{job['job_id']}/output/normalized.json",
        sha256="b" * 64,
        file_size=456,
        media_type="application/json",
    )

    assert relation["confirmation_status"] == "confirmed"
    assert evidence["storage_backend"] == "filesystem"
    assert artifact["storage_root_version"] == "data-v1"
    assert application.list_evidence(
        customer["customer_id"], system["system_id"], job["job_id"]
    ) == [evidence]
    assert application.list_artifacts(
        customer["customer_id"], system["system_id"], job["job_id"]
    ) == [artifact]


def test_cross_tenant_nodes_and_jobs_are_rejected(tmp_path: Path) -> None:
    application, _, customer_a, system_a, primary_a, _, job = _foundation(tmp_path)
    customer_b = application.create_customer(tenant_key="customer-b", name="Customer B")
    system_b = application.create_system(
        customer_b["customer_id"],
        system_key="production-db",
        name="Production DB",
        environment="production",
    )
    node_b = application.create_node(
        customer_b["customer_id"],
        system_b["system_id"],
        hostname="db-primary",
        role="Primary",
    )

    with pytest.raises(KeyError):
        application.get_node(customer_a["customer_id"], node_b["node_id"])
    with pytest.raises((IntegrityError, KeyError)):
        application.create_topology_relation(
            customer_a["customer_id"],
            system_a["system_id"],
            source_node_id=primary_a["node_id"],
            target_node_id=node_b["node_id"],
            relation_type="streams_to",
        )
    with pytest.raises(ValueError, match="another tenant"):
        application.associate_job(
            customer_b["customer_id"], system_b["system_id"], job["job_id"]
        )


def test_storage_keys_hashes_and_uniqueness_are_validated(tmp_path: Path) -> None:
    application, _, customer, system, primary, _, job = _foundation(tmp_path)
    common = dict(
        customer_id=customer["customer_id"],
        system_id=system["system_id"],
        job_id=job["job_id"],
        node_id=primary["node_id"],
        category="os",
        sha256="c" * 64,
        file_size=1,
        media_type="text/plain",
    )
    with pytest.raises(ValueError, match="safe relative"):
        application.register_evidence(storage_key="../escape.txt", **common)
    with pytest.raises(ValueError, match="sha256"):
        application.register_evidence(storage_key="input/check.txt", **{**common, "sha256": "bad"})

    application.register_evidence(storage_key="input/check.txt", **common)
    with pytest.raises(IntegrityError):
        application.register_evidence(storage_key="input/check.txt", **common)


def test_m9_3_jobs_remain_valid_without_application_scope(tmp_path: Path) -> None:
    application, jobs = _stores(tmp_path)
    job = jobs.create(JobConfig.model_validate(_config()))

    assert job["customer_id"] is None
    assert job["system_id"] is None
    assert application.list_evidence("missing", "missing", job["job_id"]) == []
