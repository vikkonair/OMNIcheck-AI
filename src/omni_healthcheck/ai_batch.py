"""Durable, single-worker controlled batches for Section AI drafts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Table, Text,
    UniqueConstraint, insert, select, update,
)
from sqlalchemy.engine import Engine

from omni_healthcheck.database import SCHEMA, metadata
from omni_healthcheck.section_persistence import (
    SectionRevisionConflictError, SectionWorkflowStore, section_workflow_items,
    section_workflows,
)


ai_draft_batches = Table(
    "ai_draft_batches", metadata,
    Column("batch_id", String(32), primary_key=True),
    Column("job_id", String(32), ForeignKey(f"{SCHEMA}.jobs.job_id", ondelete="CASCADE"), nullable=False),
    Column("actor", String(128), nullable=False),
    Column("status", String(24), nullable=False),
    Column("total_items", Integer, nullable=False),
    Column("completed_items", Integer, nullable=False),
    Column("succeeded_items", Integer, nullable=False),
    Column("fallback_items", Integer, nullable=False),
    Column("conflict_items", Integer, nullable=False),
    Column("claimed_by", Text), Column("claimed_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True)),
    CheckConstraint("status IN ('queued','running','completed','partial','failed')", name="ck_ai_draft_batches_status"),
)

ai_draft_batch_items = Table(
    "ai_draft_batch_items", metadata,
    Column("batch_item_id", String(32), primary_key=True),
    Column("batch_id", String(32), ForeignKey(f"{SCHEMA}.ai_draft_batches.batch_id", ondelete="CASCADE"), nullable=False),
    Column("item_id", String(32), ForeignKey(f"{SCHEMA}.section_workflow_items.item_id", ondelete="CASCADE"), nullable=False),
    Column("expected_revision", Integer, nullable=False), Column("ordinal", Integer, nullable=False),
    Column("status", String(24), nullable=False), Column("request_id", String(32)), Column("error", Text),
    Column("started_at", DateTime(timezone=True)), Column("completed_at", DateTime(timezone=True)),
    UniqueConstraint("batch_id", "item_id", name="uq_ai_batch_item"),
    CheckConstraint("status IN ('queued','running','ai_drafted','fallback','conflict')", name="ck_ai_draft_batch_items_status"),
)


def _now() -> datetime:
    return datetime.now(UTC)


def _serialize(row) -> dict:
    result = dict(row)
    for key, value in list(result.items()):
        if isinstance(value, datetime):
            result[key] = (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()
    return result


class AIDraftBatchStore:
    def __init__(self, *, engine: Engine, max_items: int = 5):
        if max_items < 1 or max_items > 20:
            raise ValueError("AI batch max items must be between 1 and 20")
        self.engine = engine
        self.max_items = max_items

    def create(self, job_id: str, actor: str, items: list[dict]) -> dict:
        if not actor.strip():
            raise ValueError("actor is required")
        if not items or len(items) > self.max_items:
            raise ValueError(f"batch must contain 1 to {self.max_items} items")
        item_ids = [str(item["item_id"]) for item in items]
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("batch contains duplicate section items")
        now, batch_id = _now(), uuid4().hex
        with self.engine.begin() as connection:
            rows = connection.execute(
                select(section_workflow_items.c.item_id, section_workflow_items.c.current_revision,
                       section_workflow_items.c.workflow_status)
                .join(section_workflows)
                .where(section_workflows.c.job_id == job_id,
                       section_workflow_items.c.item_id.in_(item_ids))
            ).mappings().all()
            by_id = {row["item_id"]: row for row in rows}
            if set(by_id) != set(item_ids):
                raise KeyError("one or more section items do not belong to the job")
            for item in items:
                row = by_id[str(item["item_id"])]
                if row["workflow_status"] not in {"generated", "ai_drafted"}:
                    raise ValueError("reviewed or approved content cannot enter an AI batch")
                if row["current_revision"] != int(item["expected_revision"]):
                    raise SectionRevisionConflictError(
                        f"expected revision {item['expected_revision']}, current revision is {row['current_revision']}"
                    )
            connection.execute(insert(ai_draft_batches).values(
                batch_id=batch_id, job_id=job_id, actor=actor.strip(), status="queued",
                total_items=len(items), completed_items=0, succeeded_items=0,
                fallback_items=0, conflict_items=0, created_at=now, updated_at=now,
            ))
            connection.execute(insert(ai_draft_batch_items), [
                {"batch_item_id": uuid4().hex, "batch_id": batch_id,
                 "item_id": str(item["item_id"]), "expected_revision": int(item["expected_revision"]),
                 "ordinal": ordinal, "status": "queued"}
                for ordinal, item in enumerate(items)
            ])
        return self.get(job_id, batch_id)

    def create_all_generated(self, job_id: str, actor: str) -> list[dict]:
        """Queue every generated visible Section in bounded durable batches."""
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(
                    section_workflow_items.c.item_id,
                    section_workflow_items.c.current_revision,
                )
                .join(section_workflows)
                .where(
                    section_workflows.c.job_id == job_id,
                    section_workflow_items.c.workflow_status == "generated",
                )
                .order_by(section_workflow_items.c.section_id, section_workflow_items.c.section_key)
            ).mappings().all()
        items = [
            {"item_id": row["item_id"], "expected_revision": row["current_revision"]}
            for row in rows
        ]
        return [
            self.create(job_id, actor, items[start : start + self.max_items])
            for start in range(0, len(items), self.max_items)
        ]

    def get(self, job_id: str, batch_id: str) -> dict:
        with self.engine.connect() as connection:
            batch = connection.execute(select(ai_draft_batches).where(
                ai_draft_batches.c.job_id == job_id, ai_draft_batches.c.batch_id == batch_id
            )).mappings().first()
            if batch is None:
                raise KeyError(batch_id)
            items = connection.execute(select(ai_draft_batch_items).where(
                ai_draft_batch_items.c.batch_id == batch_id
            ).order_by(ai_draft_batch_items.c.ordinal)).mappings().all()
        return {**_serialize(batch), "items": [_serialize(row) for row in items]}

    def list_for_job(self, job_id: str) -> list[dict]:
        with self.engine.connect() as connection:
            batch_ids = connection.scalars(
                select(ai_draft_batches.c.batch_id)
                .where(ai_draft_batches.c.job_id == job_id)
                .order_by(ai_draft_batches.c.created_at)
            ).all()
        return [self.get(job_id, str(batch_id)) for batch_id in batch_ids]

    def claim_next(self, worker_id: str) -> dict | None:
        now = _now()
        with self.engine.begin() as connection:
            row = connection.execute(select(ai_draft_batches).where(
                ai_draft_batches.c.status == "queued"
            ).order_by(ai_draft_batches.c.created_at).limit(1).with_for_update(skip_locked=True)).mappings().first()
            if row is None:
                return None
            connection.execute(update(ai_draft_batches).where(
                ai_draft_batches.c.batch_id == row["batch_id"], ai_draft_batches.c.status == "queued"
            ).values(status="running", claimed_by=worker_id, claimed_at=now, updated_at=now))
        return self.get(row["job_id"], row["batch_id"])

    def finish_item(self, batch_id: str, batch_item_id: str, *, status: str,
                    request_id: str | None = None, error: str | None = None) -> None:
        if status not in {"ai_drafted", "fallback", "conflict"}:
            raise ValueError("invalid terminal batch item status")
        now = _now()
        with self.engine.begin() as connection:
            connection.execute(update(ai_draft_batch_items).where(
                ai_draft_batch_items.c.batch_item_id == batch_item_id
            ).values(status=status, request_id=request_id, error=error, completed_at=now))
            values = {"completed_items": ai_draft_batches.c.completed_items + 1,
                      "claimed_at": now, "updated_at": now}
            counter = {"ai_drafted": "succeeded_items", "fallback": "fallback_items", "conflict": "conflict_items"}[status]
            values[counter] = getattr(ai_draft_batches.c, counter) + 1
            connection.execute(update(ai_draft_batches).where(ai_draft_batches.c.batch_id == batch_id).values(**values))

    def finalize(self, job_id: str, batch_id: str) -> dict:
        batch = self.get(job_id, batch_id)
        if batch["completed_items"] != batch["total_items"]:
            raise RuntimeError("AI batch still has unfinished items")
        status = "completed" if batch["succeeded_items"] == batch["total_items"] else (
            "failed" if batch["succeeded_items"] == 0 else "partial"
        )
        now = _now()
        with self.engine.begin() as connection:
            connection.execute(update(ai_draft_batches).where(
                ai_draft_batches.c.batch_id == batch_id
            ).values(status=status, completed_at=now, updated_at=now))
        return self.get(job_id, batch_id)

    def recover_stale(self, stale_seconds: int) -> int:
        cutoff = _now() - timedelta(seconds=stale_seconds)
        with self.engine.begin() as connection:
            rows = connection.execute(select(ai_draft_batches.c.batch_id).where(
                ai_draft_batches.c.status == "running", ai_draft_batches.c.claimed_at < cutoff
            )).all()
            ids = [row[0] for row in rows]
            if ids:
                connection.execute(update(ai_draft_batches).where(ai_draft_batches.c.batch_id.in_(ids)).values(
                    status="queued", claimed_by=None, claimed_at=None, updated_at=_now()
                ))
            return len(ids)
