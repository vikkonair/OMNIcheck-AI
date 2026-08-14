"""M9.4 tenant-scoped application data foundation.

The existing pipeline remains file/Canonical-JSON based.  These tables provide
the durable customer, system, topology, evidence, and artifact identities that
later persistence milestones project into.
"""

from __future__ import annotations

import re
import hashlib
from datetime import UTC, datetime
from pathlib import PurePosixPath
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKeyConstraint,
    String,
    Table,
    Text,
    UniqueConstraint,
    insert,
    func,
    select,
    update,
)
from sqlalchemy.engine import Engine, RowMapping

from omni_healthcheck.database import SCHEMA, create_database_engine, jobs, metadata


CUSTOMER_STATUSES = {"active", "inactive"}
SYSTEM_STATUSES = {"active", "inactive", "retired"}
NODE_ROLES = {"Primary", "Standby", "DR", "Witness"}
CONFIRMATION_STATUSES = {"confirmed", "pending", "rejected"}
ARCHIVE_STATUSES = {"active", "archived", "pending_delete", "deleted"}
TENANT_KEY = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


customers = Table(
    "customers",
    metadata,
    Column("customer_id", String(32), primary_key=True),
    Column("tenant_key", String(64), nullable=False, unique=True),
    Column("name", Text, nullable=False),
    Column("status", String(16), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("status IN ('active', 'inactive')", name="ck_customers_status"),
)

systems = Table(
    "systems",
    metadata,
    Column("system_id", String(32), primary_key=True),
    Column("customer_id", String(32), nullable=False),
    Column("system_key", String(64), nullable=False),
    Column("name", Text, nullable=False),
    Column("environment", String(32), nullable=False),
    Column("product", String(32)),
    Column("status", String(16), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["customer_id"],
        [f"{SCHEMA}.customers.customer_id"],
        ondelete="RESTRICT",
        name="fk_systems_customer",
    ),
    UniqueConstraint("customer_id", "system_key", name="uq_systems_customer_key"),
    UniqueConstraint("system_id", "customer_id", name="uq_systems_tenant_scope"),
    CheckConstraint(
        "status IN ('active', 'inactive', 'retired')",
        name="ck_systems_status",
    ),
)

nodes = Table(
    "nodes",
    metadata,
    Column("node_id", String(32), primary_key=True),
    Column("customer_id", String(32), nullable=False),
    Column("system_id", String(32), nullable=False),
    Column("hostname", Text, nullable=False),
    Column("role", String(16), nullable=False),
    Column("product", String(32)),
    Column("confirmed", Boolean, nullable=False),
    Column("attributes", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["system_id", "customer_id"],
        [f"{SCHEMA}.systems.system_id", f"{SCHEMA}.systems.customer_id"],
        ondelete="RESTRICT",
        name="fk_nodes_system_tenant",
    ),
    UniqueConstraint("customer_id", "system_id", "hostname", name="uq_nodes_hostname"),
    UniqueConstraint(
        "node_id", "customer_id", "system_id", name="uq_nodes_tenant_scope"
    ),
    CheckConstraint(
        "role IN ('Primary', 'Standby', 'DR', 'Witness')",
        name="ck_nodes_role",
    ),
)

topology_relations = Table(
    "topology_relations",
    metadata,
    Column("relation_id", String(32), primary_key=True),
    Column("customer_id", String(32), nullable=False),
    Column("system_id", String(32), nullable=False),
    Column("source_node_id", String(32), nullable=False),
    Column("target_node_id", String(32), nullable=False),
    Column("relation_type", String(32), nullable=False),
    Column("confirmation_status", String(24), nullable=False),
    Column("evidence", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["source_node_id", "customer_id", "system_id"],
        [
            f"{SCHEMA}.nodes.node_id",
            f"{SCHEMA}.nodes.customer_id",
            f"{SCHEMA}.nodes.system_id",
        ],
        ondelete="RESTRICT",
        name="fk_topology_source_tenant",
    ),
    ForeignKeyConstraint(
        ["target_node_id", "customer_id", "system_id"],
        [
            f"{SCHEMA}.nodes.node_id",
            f"{SCHEMA}.nodes.customer_id",
            f"{SCHEMA}.nodes.system_id",
        ],
        ondelete="RESTRICT",
        name="fk_topology_target_tenant",
    ),
    UniqueConstraint(
        "customer_id",
        "system_id",
        "source_node_id",
        "target_node_id",
        "relation_type",
        name="uq_topology_relation",
    ),
    CheckConstraint(
        "confirmation_status IN ('confirmed', 'pending', 'rejected')",
        name="ck_topology_confirmation",
    ),
    CheckConstraint("source_node_id <> target_node_id", name="ck_topology_distinct_nodes"),
)

evidence_files = Table(
    "evidence_files",
    metadata,
    Column("evidence_id", String(32), primary_key=True),
    Column("customer_id", String(32), nullable=False),
    Column("system_id", String(32), nullable=False),
    Column("job_id", String(32), nullable=False),
    Column("node_id", String(32)),
    Column("category", String(32), nullable=False),
    Column("storage_backend", String(32), nullable=False),
    Column("storage_root_version", String(32), nullable=False),
    Column("storage_key", Text, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("file_size", BigInteger, nullable=False),
    Column("media_type", String(128), nullable=False),
    Column("collected_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["job_id", "customer_id", "system_id"],
        [f"{SCHEMA}.jobs.job_id", f"{SCHEMA}.jobs.customer_id", f"{SCHEMA}.jobs.system_id"],
        ondelete="CASCADE",
        name="fk_evidence_job_tenant",
    ),
    ForeignKeyConstraint(
        ["node_id", "customer_id", "system_id"],
        [
            f"{SCHEMA}.nodes.node_id",
            f"{SCHEMA}.nodes.customer_id",
            f"{SCHEMA}.nodes.system_id",
        ],
        ondelete="RESTRICT",
        name="fk_evidence_node_tenant",
    ),
    UniqueConstraint("job_id", "storage_key", name="uq_evidence_job_storage_key"),
    CheckConstraint("file_size >= 0", name="ck_evidence_file_size"),
)

artifacts = Table(
    "artifacts",
    metadata,
    Column("artifact_id", String(32), primary_key=True),
    Column("customer_id", String(32), nullable=False),
    Column("system_id", String(32), nullable=False),
    Column("job_id", String(32), nullable=False),
    Column("artifact_type", String(40), nullable=False),
    Column("artifact_version", BigInteger, nullable=False),
    Column("storage_backend", String(32), nullable=False),
    Column("storage_root_version", String(32), nullable=False),
    Column("storage_key", Text, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("file_size", BigInteger, nullable=False),
    Column("media_type", String(128), nullable=False),
    Column("retention_until", DateTime(timezone=True)),
    Column("archive_status", String(24), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("archived_at", DateTime(timezone=True)),
    Column("deleted_at", DateTime(timezone=True)),
    ForeignKeyConstraint(
        ["job_id", "customer_id", "system_id"],
        [f"{SCHEMA}.jobs.job_id", f"{SCHEMA}.jobs.customer_id", f"{SCHEMA}.jobs.system_id"],
        ondelete="CASCADE",
        name="fk_artifacts_job_tenant",
    ),
    UniqueConstraint(
        "job_id", "artifact_type", "artifact_version",
        name="uq_artifacts_job_type_version",
    ),
    UniqueConstraint(
        "job_id", "storage_key", "sha256", name="uq_artifacts_job_storage_digest"
    ),
    UniqueConstraint(
        "artifact_id", "customer_id", "system_id", "job_id",
        name="uq_artifacts_tenant_scope",
    ),
    CheckConstraint("file_size >= 0", name="ck_artifacts_file_size"),
    CheckConstraint(
        "archive_status IN ('active', 'archived', 'pending_delete', 'deleted')",
        name="ck_artifacts_archive_status",
    ),
)


def _now() -> datetime:
    return datetime.now(UTC)


def _id() -> str:
    return uuid4().hex


def _serialize(row: RowMapping) -> dict:
    result = dict(row)
    for key, value in result.items():
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=UTC)
            result[key] = value.isoformat()
    return result


def _required(value: str, field: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field} must not be empty")
    return normalized


def _storage_key(value: str) -> str:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts:
        raise ValueError("storage_key must be a safe relative key")
    return path.as_posix()


def _digest(value: str) -> str:
    normalized = value.strip().lower()
    if not SHA256.fullmatch(normalized):
        raise ValueError("sha256 must contain 64 lowercase hexadecimal characters")
    return normalized


class ApplicationDataStore:
    """Tenant-scoped CRUD for M9.4 identities and file registries."""

    def __init__(self, database_url: str | None = None, *, engine: Engine | None = None):
        if engine is None and database_url is None:
            raise ValueError("database_url or engine is required")
        self.engine = engine or create_database_engine(str(database_url))

    def create_schema_for_test(self) -> None:
        # Keep standalone application-data fixtures aligned with the complete
        # metadata contract used by the queue worker.
        import omni_healthcheck.cve  # noqa: F401
        metadata.create_all(self.engine)

    def _get(self, table: Table, id_column: Column, value: str, customer_id: str) -> dict:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(table).where(id_column == value, table.c.customer_id == customer_id)
            ).mappings().first()
        if row is None:
            raise KeyError(value)
        return _serialize(row)

    def create_customer(
        self,
        *,
        tenant_key: str,
        name: str,
        status: str = "active",
        customer_id: str | None = None,
    ) -> dict:
        tenant_key = tenant_key.strip().lower()
        if not TENANT_KEY.fullmatch(tenant_key):
            raise ValueError("tenant_key must be a lowercase DNS-style key")
        if status not in CUSTOMER_STATUSES:
            raise ValueError("invalid customer status")
        now = _now()
        record = {
            "customer_id": customer_id or _id(),
            "tenant_key": tenant_key,
            "name": _required(name, "name"),
            "status": status,
            "created_at": now,
            "updated_at": now,
        }
        with self.engine.begin() as connection:
            connection.execute(insert(customers).values(**record))
        return self.get_customer(record["customer_id"])

    def get_customer(self, customer_id: str) -> dict:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(customers).where(customers.c.customer_id == customer_id)
            ).mappings().first()
        if row is None:
            raise KeyError(customer_id)
        return _serialize(row)

    def ensure_customer_system(
        self, *, customer_name: str, system_name: str, product: str | None
    ) -> tuple[dict, dict]:
        """Idempotently create a scope for a platform-admin initiated Job.

        Names are UI-facing and may contain Traditional Chinese, so immutable
        internal keys use a short SHA-256 suffix rather than lossy transliteration.
        """
        customer_name = _required(customer_name, "customer_name")
        system_name = _required(system_name, "system_name")
        with self.engine.connect() as connection:
            customer_row = connection.execute(
                select(customers).where(customers.c.name == customer_name)
            ).mappings().first()
        if customer_row is None:
            tenant_key = f"customer-{hashlib.sha256(customer_name.encode()).hexdigest()[:16]}"
            customer = self.create_customer(tenant_key=tenant_key, name=customer_name)
        else:
            customer = _serialize(customer_row)
        with self.engine.connect() as connection:
            system_row = connection.execute(
                select(systems).where(
                    systems.c.customer_id == customer["customer_id"],
                    systems.c.name == system_name,
                )
            ).mappings().first()
        if system_row is None:
            system_key = f"system-{hashlib.sha256(system_name.encode()).hexdigest()[:16]}"
            system = self.create_system(
                customer["customer_id"], system_key=system_key, name=system_name,
                environment="unspecified", product=product,
            )
        else:
            system = _serialize(system_row)
        return customer, system

    def create_system(
        self,
        customer_id: str,
        *,
        system_key: str,
        name: str,
        environment: str,
        product: str | None = None,
        status: str = "active",
        system_id: str | None = None,
    ) -> dict:
        self.get_customer(customer_id)
        if status not in SYSTEM_STATUSES:
            raise ValueError("invalid system status")
        now = _now()
        record = {
            "system_id": system_id or _id(),
            "customer_id": customer_id,
            "system_key": _required(system_key, "system_key").lower(),
            "name": _required(name, "name"),
            "environment": _required(environment, "environment"),
            "product": product,
            "status": status,
            "created_at": now,
            "updated_at": now,
        }
        with self.engine.begin() as connection:
            connection.execute(insert(systems).values(**record))
        return self.get_system(customer_id, record["system_id"])

    def get_system(self, customer_id: str, system_id: str) -> dict:
        return self._get(systems, systems.c.system_id, system_id, customer_id)

    def create_node(
        self,
        customer_id: str,
        system_id: str,
        *,
        hostname: str,
        role: str,
        product: str | None = None,
        confirmed: bool = True,
        attributes: dict | None = None,
        node_id: str | None = None,
    ) -> dict:
        self.get_system(customer_id, system_id)
        if role not in NODE_ROLES:
            raise ValueError("invalid node role")
        now = _now()
        record = {
            "node_id": node_id or _id(),
            "customer_id": customer_id,
            "system_id": system_id,
            "hostname": _required(hostname, "hostname"),
            "role": role,
            "product": product,
            "confirmed": confirmed,
            "attributes": attributes or {},
            "created_at": now,
            "updated_at": now,
        }
        with self.engine.begin() as connection:
            connection.execute(insert(nodes).values(**record))
        return self.get_node(customer_id, record["node_id"])

    def get_node(self, customer_id: str, node_id: str) -> dict:
        return self._get(nodes, nodes.c.node_id, node_id, customer_id)

    def create_topology_relation(
        self,
        customer_id: str,
        system_id: str,
        *,
        source_node_id: str,
        target_node_id: str,
        relation_type: str,
        confirmation_status: str = "confirmed",
        evidence: dict | None = None,
        relation_id: str | None = None,
    ) -> dict:
        self.get_node(customer_id, source_node_id)
        self.get_node(customer_id, target_node_id)
        if source_node_id == target_node_id:
            raise ValueError("topology relation requires two different nodes")
        if confirmation_status not in CONFIRMATION_STATUSES:
            raise ValueError("invalid confirmation status")
        now = _now()
        record = {
            "relation_id": relation_id or _id(),
            "customer_id": customer_id,
            "system_id": system_id,
            "source_node_id": source_node_id,
            "target_node_id": target_node_id,
            "relation_type": _required(relation_type, "relation_type"),
            "confirmation_status": confirmation_status,
            "evidence": evidence or {},
            "created_at": now,
            "updated_at": now,
        }
        with self.engine.begin() as connection:
            connection.execute(insert(topology_relations).values(**record))
        return self._get(
            topology_relations,
            topology_relations.c.relation_id,
            record["relation_id"],
            customer_id,
        )

    def associate_job(self, customer_id: str, system_id: str, job_id: str) -> dict:
        self.get_system(customer_id, system_id)
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(jobs.c.customer_id, jobs.c.system_id).where(jobs.c.job_id == job_id)
            ).mappings().first()
            if existing is None:
                raise KeyError(job_id)
            existing_scope = (existing["customer_id"], existing["system_id"])
            requested_scope = (customer_id, system_id)
            if existing_scope != (None, None) and existing_scope != requested_scope:
                raise ValueError("job is already associated with another tenant scope")
            result = connection.execute(
                update(jobs)
                .where(jobs.c.job_id == job_id)
                .values(customer_id=customer_id, system_id=system_id)
            )
        if result.rowcount != 1:  # pragma: no cover - protected by the locked transaction.
            raise KeyError(job_id)
        return {"job_id": job_id, "customer_id": customer_id, "system_id": system_id}

    def _job_is_scoped(self, customer_id: str, system_id: str, job_id: str) -> None:
        with self.engine.connect() as connection:
            found = connection.scalar(
                select(jobs.c.job_id).where(
                    jobs.c.job_id == job_id,
                    jobs.c.customer_id == customer_id,
                    jobs.c.system_id == system_id,
                )
            )
        if found is None:
            raise KeyError(job_id)

    def register_evidence(
        self,
        customer_id: str,
        system_id: str,
        job_id: str,
        *,
        category: str,
        storage_key: str,
        sha256: str,
        file_size: int,
        media_type: str,
        node_id: str | None = None,
        storage_backend: str = "filesystem",
        storage_root_version: str = "data-v1",
        collected_at: datetime | None = None,
        evidence_id: str | None = None,
    ) -> dict:
        self._job_is_scoped(customer_id, system_id, job_id)
        if node_id is not None:
            self.get_node(customer_id, node_id)
        if file_size < 0:
            raise ValueError("file_size must be non-negative")
        record = {
            "evidence_id": evidence_id or _id(),
            "customer_id": customer_id,
            "system_id": system_id,
            "job_id": job_id,
            "node_id": node_id,
            "category": _required(category, "category"),
            "storage_backend": _required(storage_backend, "storage_backend"),
            "storage_root_version": _required(storage_root_version, "storage_root_version"),
            "storage_key": _storage_key(storage_key),
            "sha256": _digest(sha256),
            "file_size": file_size,
            "media_type": _required(media_type, "media_type"),
            "collected_at": collected_at,
            "created_at": _now(),
        }
        with self.engine.begin() as connection:
            connection.execute(insert(evidence_files).values(**record))
        return self._get(
            evidence_files, evidence_files.c.evidence_id, record["evidence_id"], customer_id
        )

    def register_artifact(
        self,
        customer_id: str,
        system_id: str,
        job_id: str,
        *,
        artifact_type: str,
        storage_key: str,
        sha256: str,
        file_size: int,
        media_type: str,
        storage_backend: str = "filesystem",
        storage_root_version: str = "data-v1",
        retention_until: datetime | None = None,
        archive_status: str = "active",
        artifact_version: int | None = None,
        artifact_id: str | None = None,
    ) -> dict:
        self._job_is_scoped(customer_id, system_id, job_id)
        if archive_status not in ARCHIVE_STATUSES:
            raise ValueError("invalid archive status")
        if file_size < 0:
            raise ValueError("file_size must be non-negative")
        if artifact_version is not None and artifact_version < 1:
            raise ValueError("artifact_version must be positive")
        if artifact_version is None:
            with self.engine.connect() as connection:
                artifact_version = 1 + int(connection.scalar(
                    select(func.coalesce(func.max(artifacts.c.artifact_version), 0)).where(
                        artifacts.c.job_id == job_id,
                        artifacts.c.artifact_type == artifact_type,
                    )
                ) or 0)
        now = _now()
        record = {
            "artifact_id": artifact_id or _id(),
            "customer_id": customer_id,
            "system_id": system_id,
            "job_id": job_id,
            "artifact_type": _required(artifact_type, "artifact_type"),
            "artifact_version": artifact_version,
            "storage_backend": _required(storage_backend, "storage_backend"),
            "storage_root_version": _required(storage_root_version, "storage_root_version"),
            "storage_key": _storage_key(storage_key),
            "sha256": _digest(sha256),
            "file_size": file_size,
            "media_type": _required(media_type, "media_type"),
            "retention_until": retention_until,
            "archive_status": archive_status,
            "created_at": now,
            "updated_at": now,
            "archived_at": now if archive_status == "archived" else None,
            "deleted_at": now if archive_status == "deleted" else None,
        }
        with self.engine.begin() as connection:
            connection.execute(insert(artifacts).values(**record))
        return self._get(
            artifacts, artifacts.c.artifact_id, record["artifact_id"], customer_id
        )

    def list_evidence(self, customer_id: str, system_id: str, job_id: str) -> list[dict]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(evidence_files)
                .where(
                    evidence_files.c.customer_id == customer_id,
                    evidence_files.c.system_id == system_id,
                    evidence_files.c.job_id == job_id,
                )
                .order_by(evidence_files.c.created_at)
            ).mappings().all()
        return [_serialize(row) for row in rows]

    def list_artifacts(self, customer_id: str, system_id: str, job_id: str) -> list[dict]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(artifacts)
                .where(
                    artifacts.c.customer_id == customer_id,
                    artifacts.c.system_id == system_id,
                    artifacts.c.job_id == job_id,
                )
                .order_by(artifacts.c.created_at)
            ).mappings().all()
        return [_serialize(row) for row in rows]

    def get_artifact(self, customer_id: str, artifact_id: str) -> dict:
        return self._get(artifacts, artifacts.c.artifact_id, artifact_id, customer_id)
