"""M9.6 versioned Artifact Registry and copy-verify archive workflow."""

from __future__ import annotations

import hashlib
import mimetypes
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKeyConstraint,
    String,
    Table,
    Text,
    UniqueConstraint,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine

from omni_healthcheck.application_data import ApplicationDataStore, artifacts
from omni_healthcheck.database import SCHEMA, create_database_engine, metadata


artifact_relations = Table(
    "artifact_relations",
    metadata,
    Column("relation_id", String(32), primary_key=True),
    Column("customer_id", String(32), nullable=False),
    Column("system_id", String(32), nullable=False),
    Column("job_id", String(32), nullable=False),
    Column("parent_artifact_id", String(32), nullable=False),
    Column("child_artifact_id", String(32), nullable=False),
    Column("relation_type", String(32), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["parent_artifact_id", "customer_id", "system_id", "job_id"],
        [
            f"{SCHEMA}.artifacts.artifact_id",
            f"{SCHEMA}.artifacts.customer_id",
            f"{SCHEMA}.artifacts.system_id",
            f"{SCHEMA}.artifacts.job_id",
        ],
        ondelete="CASCADE",
        name="fk_artifact_relations_parent_tenant",
    ),
    ForeignKeyConstraint(
        ["child_artifact_id", "customer_id", "system_id", "job_id"],
        [
            f"{SCHEMA}.artifacts.artifact_id",
            f"{SCHEMA}.artifacts.customer_id",
            f"{SCHEMA}.artifacts.system_id",
            f"{SCHEMA}.artifacts.job_id",
        ],
        ondelete="CASCADE",
        name="fk_artifact_relations_child_tenant",
    ),
    UniqueConstraint(
        "parent_artifact_id", "child_artifact_id", "relation_type",
        name="uq_artifact_relation",
    ),
)

artifact_events = Table(
    "artifact_events",
    metadata,
    Column("event_id", String(32), primary_key=True),
    Column("artifact_id", String(32), nullable=False),
    Column("customer_id", String(32), nullable=False),
    Column("system_id", String(32), nullable=False),
    Column("job_id", String(32), nullable=False),
    Column("event_type", String(32), nullable=False),
    Column("details", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["artifact_id", "customer_id", "system_id", "job_id"],
        [
            f"{SCHEMA}.artifacts.artifact_id",
            f"{SCHEMA}.artifacts.customer_id",
            f"{SCHEMA}.artifacts.system_id",
            f"{SCHEMA}.artifacts.job_id",
        ],
        ondelete="CASCADE",
        name="fk_artifact_events_artifact_tenant",
    ),
)


OUTPUT_TYPES = {
    "inventory.json": "inventory-json",
    "topology.json": "topology-json",
    "scope-ledger.json": "scope-json",
    "normalized.json": "canonical-json",
    "configuration-comparison.json": "configuration-json",
    "assessment.json": "assessment-json",
    "section-workflow.json": "section-workflow-json",
    "coverage-ledger.json": "coverage-json",
    "qa-result.json": "qa-json",
    "report-model.json": "report-model-json",
    "v4-report.json": "v4-report-json",
    "v4-qa-result.json": "v4-qa-json",
    "report.docx": "report-docx",
    "report.pdf": "report-pdf",
}

DERIVATIONS = (
    ("assessment-json", "section-workflow-json"),
    ("canonical-json", "report-model-json"),
    ("report-model-json", "v4-report-json"),
    ("v4-report-json", "report-docx"),
    ("report-docx", "report-pdf"),
)


def _id() -> str:
    return uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_path(root: Path, storage_key: str) -> Path:
    relative = PurePosixPath(storage_key)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("storage_key must be a safe relative key")
    resolved_root = root.resolve()
    resolved = (resolved_root / Path(*relative.parts)).resolve()
    if not resolved.is_relative_to(resolved_root):
        raise ValueError("storage_key escapes configured root")
    return resolved


class ArtifactRegistry:
    """Register immutable output versions and archive due files safely."""

    def __init__(self, database_url: str | None = None, *, engine: Engine | None = None):
        if engine is None and database_url is None:
            raise ValueError("database_url or engine is required")
        self.engine = engine or create_database_engine(str(database_url))
        self.application = ApplicationDataStore(engine=self.engine)

    def _event(self, connection, artifact: dict, event_type: str, details: dict) -> None:
        connection.execute(insert(artifact_events).values(
            event_id=_id(), artifact_id=artifact["artifact_id"],
            customer_id=artifact["customer_id"], system_id=artifact["system_id"],
            job_id=artifact["job_id"], event_type=event_type,
            details=details, created_at=_now(),
        ))

    def register_outputs(
        self,
        *,
        job_id: str,
        customer_id: str,
        system_id: str,
        output_dir: Path,
        data_root: Path,
        retention_days: int = 365,
    ) -> list[dict]:
        if retention_days < 1:
            raise ValueError("retention_days must be positive")
        output_dir = output_dir.resolve()
        data_root = data_root.resolve()
        if not output_dir.is_relative_to(data_root):
            raise ValueError("output directory must be beneath data root")
        registered: list[dict] = []
        by_type: dict[str, dict] = {}
        for filename, artifact_type in OUTPUT_TYPES.items():
            path = output_dir / filename
            if not path.is_file():
                continue
            storage_key = path.relative_to(data_root).as_posix()
            digest = _sha256(path)
            with self.engine.connect() as connection:
                existing = connection.execute(select(artifacts).where(
                    artifacts.c.job_id == job_id,
                    artifacts.c.storage_key == storage_key,
                    artifacts.c.sha256 == digest,
                )).mappings().first()
                previous = connection.execute(select(artifacts).where(
                    artifacts.c.job_id == job_id,
                    artifacts.c.artifact_type == artifact_type,
                ).order_by(artifacts.c.artifact_version.desc())).mappings().first()
            if existing is None:
                artifact = self.application.register_artifact(
                    customer_id, system_id, job_id,
                    artifact_type=artifact_type,
                    storage_key=storage_key,
                    sha256=digest,
                    file_size=path.stat().st_size,
                    media_type=mimetypes.guess_type(filename)[0] or "application/octet-stream",
                    retention_until=_now() + timedelta(days=retention_days),
                )
                with self.engine.begin() as connection:
                    self._event(connection, artifact, "registered", {"filename": filename})
                    if previous is not None:
                        connection.execute(insert(artifact_relations).values(
                            relation_id=_id(), customer_id=customer_id,
                            system_id=system_id, job_id=job_id,
                            parent_artifact_id=previous["artifact_id"],
                            child_artifact_id=artifact["artifact_id"],
                            relation_type="supersedes", created_at=_now(),
                        ))
            else:
                artifact = dict(existing)
            registered.append(artifact)
            by_type[artifact_type] = artifact

        with self.engine.begin() as connection:
            for parent_type, child_type in DERIVATIONS:
                parent = by_type.get(parent_type)
                child = by_type.get(child_type)
                if parent is None or child is None:
                    continue
                found = connection.scalar(select(artifact_relations.c.relation_id).where(
                    artifact_relations.c.parent_artifact_id == parent["artifact_id"],
                    artifact_relations.c.child_artifact_id == child["artifact_id"],
                    artifact_relations.c.relation_type == "derived_from",
                ))
                if found is None:
                    connection.execute(insert(artifact_relations).values(
                        relation_id=_id(), customer_id=customer_id, system_id=system_id,
                        job_id=job_id, parent_artifact_id=parent["artifact_id"],
                        child_artifact_id=child["artifact_id"],
                        relation_type="derived_from", created_at=_now(),
                    ))
        return registered

    def archive_due(
        self,
        *,
        active_root: Path,
        archive_root: Path,
        as_of: datetime | None = None,
        apply: bool = False,
    ) -> list[dict]:
        as_of = as_of or _now()
        with self.engine.connect() as connection:
            due = connection.execute(select(artifacts).where(
                artifacts.c.archive_status == "active",
                artifacts.c.retention_until.is_not(None),
                artifacts.c.retention_until <= as_of,
                artifacts.c.storage_backend == "filesystem",
            ).order_by(artifacts.c.created_at)).mappings().all()
        results = []
        for row in due:
            artifact = dict(row)
            source = _safe_path(active_root, artifact["storage_key"])
            target_key = (
                PurePosixPath("artifacts") / artifact["customer_id"] /
                artifact["job_id"] / artifact["artifact_id"] / source.name
            ).as_posix()
            result = {"artifact_id": artifact["artifact_id"], "source": str(source),
                      "archive_key": target_key, "applied": False}
            if apply:
                if not source.is_file():
                    raise FileNotFoundError(source)
                if _sha256(source) != artifact["sha256"]:
                    raise RuntimeError(f"source hash mismatch: {artifact['artifact_id']}")
                target = _safe_path(archive_root, target_key)
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_suffix(target.suffix + ".partial")
                shutil.copy2(source, temporary)
                if _sha256(temporary) != artifact["sha256"]:
                    temporary.unlink(missing_ok=True)
                    raise RuntimeError(f"archive hash mismatch: {artifact['artifact_id']}")
                temporary.replace(target)
                now = _now()
                with self.engine.begin() as connection:
                    connection.execute(update(artifacts).where(
                        artifacts.c.artifact_id == artifact["artifact_id"]
                    ).values(
                        storage_root_version="archive-v1", storage_key=target_key,
                        archive_status="archived", archived_at=now, updated_at=now,
                    ))
                    self._event(connection, artifact, "archived", {
                        "source_preserved": True, "archive_key": target_key,
                    })
                result["applied"] = True
            results.append(result)
        return results

    def list_relations(self, customer_id: str, job_id: str) -> list[dict]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(artifact_relations).where(
                artifact_relations.c.customer_id == customer_id,
                artifact_relations.c.job_id == job_id,
            ).order_by(artifact_relations.c.created_at)).mappings().all()
        return [dict(row) for row in rows]

    def request_delete(self, customer_id: str, artifact_id: str, *, reason: str) -> dict:
        reason = reason.strip()
        if not reason:
            raise ValueError("delete reason must not be empty")
        with self.engine.begin() as connection:
            artifact = connection.execute(select(artifacts).where(
                artifacts.c.customer_id == customer_id,
                artifacts.c.artifact_id == artifact_id,
            )).mappings().first()
            if artifact is None:
                raise KeyError(artifact_id)
            if artifact["archive_status"] != "archived":
                raise ValueError("only archived artifacts can be marked pending_delete")
            connection.execute(update(artifacts).where(
                artifacts.c.artifact_id == artifact_id
            ).values(archive_status="pending_delete", updated_at=_now()))
            self._event(connection, dict(artifact), "delete_requested", {"reason": reason})
        return self.application.get_artifact(customer_id, artifact_id)

    def cancel_delete(self, customer_id: str, artifact_id: str, *, reason: str) -> dict:
        reason = reason.strip()
        if not reason:
            raise ValueError("cancel reason must not be empty")
        with self.engine.begin() as connection:
            artifact = connection.execute(select(artifacts).where(
                artifacts.c.customer_id == customer_id,
                artifacts.c.artifact_id == artifact_id,
            )).mappings().first()
            if artifact is None:
                raise KeyError(artifact_id)
            if artifact["archive_status"] != "pending_delete":
                raise ValueError("artifact is not pending_delete")
            connection.execute(update(artifacts).where(
                artifacts.c.artifact_id == artifact_id
            ).values(archive_status="archived", updated_at=_now()))
            self._event(connection, dict(artifact), "delete_cancelled", {"reason": reason})
        return self.application.get_artifact(customer_id, artifact_id)

    def list_events(self, customer_id: str, artifact_id: str) -> list[dict]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(artifact_events).where(
                artifact_events.c.customer_id == customer_id,
                artifact_events.c.artifact_id == artifact_id,
            ).order_by(artifact_events.c.created_at)).mappings().all()
        return [dict(row) for row in rows]
