"""EDB audit storage for optional AI Gateway calls."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Table, Text, insert, select, update
from sqlalchemy.engine import Engine

from omni_healthcheck.database import SCHEMA, create_database_engine, metadata


ai_gateway_requests = Table(
    "ai_gateway_requests",
    metadata,
    Column("request_id", String(32), primary_key=True),
    Column("job_id", String(32), ForeignKey(f"{SCHEMA}.jobs.job_id", ondelete="CASCADE"), nullable=False),
    Column("item_id", String(32), ForeignKey(f"{SCHEMA}.section_workflow_items.item_id", ondelete="CASCADE"), nullable=False),
    Column("provider", String(32), nullable=False),
    Column("model", String(128), nullable=False),
    Column("prompt_version", String(32), nullable=False),
    Column("requested_by", String(128), nullable=False),
    Column("status", String(24), nullable=False),
    Column("attempts", Integer, nullable=False),
    Column("duration_ms", Integer),
    Column("prompt_sha256", String(64), nullable=False),
    Column("response_sha256", String(64)),
    Column("sanitized_prompt", JSON, nullable=False),
    Column("sanitized_response", JSON),
    Column("usage", JSON),
    Column("error_type", String(64)),
    Column("error_message", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True)),
    CheckConstraint(
        "status IN ('started','succeeded','failed','discarded_stale')",
        name="ck_ai_gateway_requests_status",
    ),
)


def _now() -> datetime:
    return datetime.now(UTC)


class AIGatewayAuditStore:
    def __init__(self, database_url: str | None = None, *, engine: Engine | None = None):
        if engine is None and database_url is None:
            raise ValueError("database_url or engine is required")
        self.engine = engine or create_database_engine(str(database_url))

    def start(self, *, job_id: str, item_id: str, provider: str, model: str,
              prompt_version: str, requested_by: str, prompt_sha256: str,
              sanitized_prompt: dict) -> str:
        request_id = uuid4().hex
        with self.engine.begin() as connection:
            connection.execute(insert(ai_gateway_requests).values(
                request_id=request_id, job_id=job_id, item_id=item_id,
                provider=provider, model=model, prompt_version=prompt_version,
                requested_by=requested_by,
                status="started", attempts=0, prompt_sha256=prompt_sha256,
                sanitized_prompt=sanitized_prompt, created_at=_now(),
            ))
        return request_id

    def finish(self, request_id: str, *, status: str, attempts: int,
               duration_ms: int, response_sha256: str | None = None,
               sanitized_response: dict | None = None, usage: dict | None = None,
               error_type: str | None = None, error_message: str | None = None) -> None:
        safe_error = error_message[:1000] if error_message else None
        with self.engine.begin() as connection:
            connection.execute(
                update(ai_gateway_requests)
                .where(ai_gateway_requests.c.request_id == request_id)
                .values(
                    status=status, attempts=attempts, duration_ms=duration_ms,
                    response_sha256=response_sha256,
                    sanitized_response=sanitized_response, usage=usage,
                    error_type=error_type, error_message=safe_error,
                    completed_at=_now(),
                )
            )

    def list_for_job(self, job_id: str) -> list[dict]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(ai_gateway_requests)
                .where(ai_gateway_requests.c.job_id == job_id)
                .order_by(ai_gateway_requests.c.created_at)
            ).mappings().all()
        return [dict(row) for row in rows]

    def mark_discarded_stale(self, request_id: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                update(ai_gateway_requests)
                .where(ai_gateway_requests.c.request_id == request_id)
                .values(
                    status="discarded_stale",
                    error_type="SectionRevisionConflictError",
                    error_message=(
                        "AI draft discarded because the Section revision changed"
                    ),
                    completed_at=_now(),
                )
            )
