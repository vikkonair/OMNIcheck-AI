"""EDB persistence and optimistic-concurrency workflow transitions."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine

from omni_healthcheck.database import SCHEMA, create_database_engine, metadata
from omni_healthcheck.section_workflow import (
    SectionWorkflowDocument,
    SectionWorkflowItem,
    approve_review,
    attach_ai_draft,
    review_draft,
)


section_workflows = Table(
    "section_workflows",
    metadata,
    Column("workflow_id", String(32), primary_key=True),
    Column("job_id", String(32), ForeignKey(f"{SCHEMA}.jobs.job_id", ondelete="CASCADE"), nullable=False),
    Column("schema_version", String(16), nullable=False),
    Column("ruleset_version", String(32), nullable=False),
    Column("ai_enabled", Boolean, nullable=False),
    Column("renderer_uses_ai", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("job_id", name="uq_section_workflows_job"),
)

section_workflow_items = Table(
    "section_workflow_items",
    metadata,
    Column("item_id", String(32), primary_key=True),
    Column("workflow_id", String(32), ForeignKey(f"{SCHEMA}.section_workflows.workflow_id", ondelete="CASCADE"), nullable=False),
    Column("section_key", Text, nullable=False),
    Column("section_id", String(24), nullable=False),
    Column("check_id", String(80), nullable=False),
    Column("node", Text, nullable=False),
    Column("status", String(16), nullable=False),
    Column("workflow_status", String(16), nullable=False),
    Column("current_revision", Integer, nullable=False),
    Column("selected_source", String(32), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("workflow_id", "section_key", name="uq_section_items_key"),
    CheckConstraint(
        "workflow_status IN ('generated','ai_drafted','reviewed','approved')",
        name="ck_section_items_workflow_status",
    ),
    CheckConstraint(
        "selected_source IN ('deterministic_template','approved')",
        name="ck_section_items_selected_source",
    ),
)

section_workflow_revisions = Table(
    "section_workflow_revisions",
    metadata,
    Column("revision_id", String(32), primary_key=True),
    Column("item_id", String(32), ForeignKey(f"{SCHEMA}.section_workflow_items.item_id", ondelete="CASCADE"), nullable=False),
    Column("revision", Integer, nullable=False),
    Column("action", String(24), nullable=False),
    Column("actor", String(128), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("content_sha256", String(64), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("item_id", "revision", name="uq_section_revisions_item_revision"),
    CheckConstraint(
        "action IN ('generated','ai_drafted','reviewed','approved')",
        name="ck_section_revisions_action",
    ),
)


class SectionRevisionConflictError(RuntimeError):
    """Raised when an engineer writes against a stale revision."""


def _now() -> datetime:
    return datetime.now(UTC)


def _id() -> str:
    return uuid4().hex


def _payload(item: SectionWorkflowItem) -> dict:
    return item.model_dump(mode="json")


def _digest(payload: dict) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class SectionWorkflowStore:
    def __init__(self, database_url: str | None = None, *, engine: Engine | None = None):
        if engine is None and database_url is None:
            raise ValueError("database_url or engine is required")
        self.engine = engine or create_database_engine(str(database_url))

    def persist_baseline(self, job_id: str, document: SectionWorkflowDocument) -> dict:
        """Persist once. A rerun never overwrites engineer or approval history."""

        now = _now()
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(section_workflows).where(section_workflows.c.job_id == job_id)
            ).mappings().first()
            if existing is not None:
                return {"workflow_id": existing["workflow_id"], "created": False}
            workflow_id = _id()
            connection.execute(insert(section_workflows).values(
                workflow_id=workflow_id,
                job_id=job_id,
                schema_version=document.schema_version,
                ruleset_version=document.ruleset_version,
                ai_enabled=document.ai_enabled,
                renderer_uses_ai=False,
                created_at=now,
                updated_at=now,
            ))
            for item in document.items:
                item_id = _id()
                payload = _payload(item)
                connection.execute(insert(section_workflow_items).values(
                    item_id=item_id,
                    workflow_id=workflow_id,
                    section_key=item.section_key,
                    section_id=item.section_id,
                    check_id=item.check_id,
                    node=item.node,
                    status=item.status,
                    workflow_status=item.workflow_status,
                    current_revision=item.revision,
                    selected_source=item.selected_source,
                    payload=payload,
                    updated_at=now,
                ))
                self._append_revision(
                    connection, item_id, item, action="generated", actor="system"
                )
        return {"workflow_id": workflow_id, "created": True}

    @staticmethod
    def _append_revision(connection, item_id: str, item: SectionWorkflowItem, *, action: str, actor: str) -> None:
        payload = _payload(item)
        connection.execute(insert(section_workflow_revisions).values(
            revision_id=_id(), item_id=item_id, revision=item.revision,
            action=action, actor=actor, payload=payload,
            content_sha256=_digest(payload), created_at=_now(),
        ))

    def document(self, job_id: str) -> SectionWorkflowDocument:
        with self.engine.connect() as connection:
            workflow = connection.execute(
                select(section_workflows).where(section_workflows.c.job_id == job_id)
            ).mappings().first()
            if workflow is None:
                raise KeyError(job_id)
            rows = connection.execute(
                select(section_workflow_items)
                .where(section_workflow_items.c.workflow_id == workflow["workflow_id"])
                .order_by(section_workflow_items.c.section_id, section_workflow_items.c.section_key)
            ).mappings().all()
        return SectionWorkflowDocument(
            schema_version=workflow["schema_version"],
            ruleset_version=workflow["ruleset_version"],
            ai_enabled=workflow["ai_enabled"],
            renderer_uses_ai=False,
            items=[SectionWorkflowItem.model_validate(row["payload"]) for row in rows],
        )

    def list_items(self, job_id: str) -> list[dict]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(section_workflow_items.c.item_id, section_workflow_items.c.payload)
                .join(section_workflows)
                .where(section_workflows.c.job_id == job_id)
                .order_by(section_workflow_items.c.section_id, section_workflow_items.c.section_key)
            ).mappings().all()
        if not rows:
            with self.engine.connect() as connection:
                exists = connection.scalar(
                    select(section_workflows.c.workflow_id).where(section_workflows.c.job_id == job_id)
                )
            if exists is None:
                raise KeyError(job_id)
        return [{"item_id": row["item_id"], **row["payload"]} for row in rows]

    def get_item(self, job_id: str, item_id: str) -> SectionWorkflowItem:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(section_workflow_items.c.payload)
                .join(section_workflows)
                .where(
                    section_workflows.c.job_id == job_id,
                    section_workflow_items.c.item_id == item_id,
                )
            ).mappings().first()
        if row is None:
            raise KeyError(item_id)
        return SectionWorkflowItem.model_validate(row["payload"])

    def revisions(self, job_id: str, item_id: str) -> list[dict]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(section_workflow_revisions)
                .select_from(
                    section_workflow_revisions
                    .join(
                        section_workflow_items,
                        section_workflow_revisions.c.item_id
                        == section_workflow_items.c.item_id,
                    )
                    .join(
                        section_workflows,
                        section_workflow_items.c.workflow_id
                        == section_workflows.c.workflow_id,
                    )
                )
                .where(section_workflows.c.job_id == job_id, section_workflow_items.c.item_id == item_id)
                .order_by(section_workflow_revisions.c.revision)
            ).mappings().all()
        return [dict(row) for row in rows]

    def transition(
        self,
        job_id: str,
        item_id: str,
        *,
        expected_revision: int,
        action: str,
        actor: str,
        observation: str | None = None,
        recommendation: str | None = None,
    ) -> dict:
        if not actor.strip():
            raise ValueError("actor is required")
        with self.engine.begin() as connection:
            row = connection.execute(
                select(section_workflow_items)
                .join(section_workflows)
                .where(
                    section_workflows.c.job_id == job_id,
                    section_workflow_items.c.item_id == item_id,
                )
                .with_for_update()
            ).mappings().first()
            if row is None:
                raise KeyError(item_id)
            if row["current_revision"] != expected_revision:
                raise SectionRevisionConflictError(
                    f"expected revision {expected_revision}, current revision is {row['current_revision']}"
                )
            current = SectionWorkflowItem.model_validate(row["payload"])
            if action in {"ai_drafted", "reviewed"}:
                if not observation or not recommendation:
                    raise ValueError("observation and recommendation are required")
                changed = (
                    attach_ai_draft(current, observation=observation, recommendation=recommendation)
                    if action == "ai_drafted"
                    else review_draft(current, observation=observation, recommendation=recommendation)
                )
            elif action == "approved":
                changed = approve_review(current)
            else:
                raise ValueError(f"unsupported workflow action: {action}")
            payload = _payload(changed)
            result = connection.execute(
                update(section_workflow_items)
                .where(
                    section_workflow_items.c.item_id == item_id,
                    section_workflow_items.c.current_revision == expected_revision,
                )
                .values(
                    workflow_status=changed.workflow_status,
                    current_revision=changed.revision,
                    selected_source=changed.selected_source,
                    payload=payload,
                    updated_at=_now(),
                )
            )
            if result.rowcount != 1:
                raise SectionRevisionConflictError("section revision changed concurrently")
            self._append_revision(
                connection, item_id, changed, action=action, actor=actor.strip()
            )
            connection.execute(
                update(section_workflows)
                .where(section_workflows.c.workflow_id == row["workflow_id"])
                .values(updated_at=_now(), renderer_uses_ai=False)
            )
        return {"item_id": item_id, **payload}
