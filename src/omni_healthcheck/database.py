"""EDB/PostgreSQL metadata storage and durable M9.3 job queue."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    Column,
    CheckConstraint,
    ForeignKeyConstraint,
    create_engine,
    event,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.engine import Engine, RowMapping


SCHEMA = "omnicheck"
metadata = MetaData(schema=SCHEMA)

jobs = Table(
    "jobs",
    metadata,
    Column("job_id", String(32), primary_key=True),
    Column("customer_id", String(32)),
    Column("system_id", String(32)),
    Column("customer", Text, nullable=False),
    Column("system_name", Text),
    Column("period", Text, nullable=False),
    Column("product", String(32), nullable=False),
    Column("status", String(20), nullable=False, index=True),
    Column("error", Text),
    Column("input_files", Integer, nullable=False, default=0),
    Column("attempts", Integer, nullable=False, default=0),
    Column("max_attempts", Integer, nullable=False, default=3),
    Column("claimed_by", Text),
    Column("claimed_at", DateTime(timezone=True)),
    Column("available_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "job_id",
        "customer_id",
        "system_id",
        name="uq_jobs_tenant_scope",
    ),
    ForeignKeyConstraint(
        ["customer_id"],
        [f"{SCHEMA}.customers.customer_id"],
        ondelete="RESTRICT",
        name="fk_jobs_customer",
    ),
    ForeignKeyConstraint(
        ["system_id", "customer_id"],
        [f"{SCHEMA}.systems.system_id", f"{SCHEMA}.systems.customer_id"],
        ondelete="RESTRICT",
        name="fk_jobs_system_tenant",
    ),
    CheckConstraint(
        "system_id IS NULL OR customer_id IS NOT NULL",
        name="ck_jobs_system_requires_customer",
    ),
)

job_events = Table(
    "job_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "job_id",
        String(32),
        ForeignKey(f"{SCHEMA}.jobs.job_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("event_type", String(40), nullable=False),
    Column("status", String(20), nullable=False),
    Column("worker_id", Text),
    Column("detail", JSON),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


def _now() -> datetime:
    return datetime.now(UTC)


class JobLeaseLostError(RuntimeError):
    """Raised when a worker no longer owns the job it is completing."""


def create_database_engine(database_url: str) -> Engine:
    options: dict[str, Any] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        options["execution_options"] = {"schema_translate_map": {SCHEMA: None}}
    else:
        # EPAS can default to Redwood DateStyle, whose timestamptz text format
        # psycopg 3 intentionally does not parse.  Keep the database-wide
        # compatibility mode unchanged and normalize only OMNIcheck sessions.
        options["connect_args"] = {"options": "-c DateStyle=ISO"}
    engine = create_engine(database_url, **options)
    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection: Any, _: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


def _serialize(row: RowMapping) -> dict:
    result = dict(row)
    for key in ("created_at", "updated_at", "claimed_at", "available_at"):
        value = result.get(key)
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=UTC)
            result[key] = value.isoformat()
    return result


def _json_safe(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def queue_claim_statement(now: datetime) -> Any:
    return (
        select(jobs)
        .where(
            jobs.c.status == "queued",
            jobs.c.available_at <= now,
            jobs.c.attempts < jobs.c.max_attempts,
        )
        .order_by(jobs.c.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )


class DatabaseMetadataStore:
    """Persist job state and claim queued work using row locks."""

    def __init__(self, database_url: str):
        self.engine = create_database_engine(database_url)

    def create_schema_for_test(self) -> None:
        """Create tables for isolated tests; production uses Alembic."""
        # Registers the M9.4 tables referenced by nullable job tenant keys.
        import omni_healthcheck.application_data  # noqa: F401
        import omni_healthcheck.pipeline_persistence  # noqa: F401
        import omni_healthcheck.artifact_lifecycle  # noqa: F401
        import omni_healthcheck.section_persistence  # noqa: F401
        import omni_healthcheck.ai_persistence  # noqa: F401
        import omni_healthcheck.ai_batch  # noqa: F401

        metadata.create_all(self.engine)

    def ping(self) -> None:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def _event(
        self,
        connection: Any,
        job_id: str,
        event_type: str,
        status: str,
        *,
        worker_id: str | None = None,
        detail: dict | None = None,
    ) -> None:
        connection.execute(
            insert(job_events).values(
                job_id=job_id,
                event_type=event_type,
                status=status,
                worker_id=worker_id,
                detail=detail,
                created_at=_now(),
            )
        )

    def create(self, value: dict) -> dict:
        now = _now()
        record = {
            **value,
            "attempts": 0,
            "max_attempts": 3,
            "claimed_by": None,
            "claimed_at": None,
            "available_at": now,
            "created_at": now,
            "updated_at": now,
        }
        with self.engine.begin() as connection:
            connection.execute(insert(jobs).values(**record))
            self._event(connection, value["job_id"], "created", value["status"])
        return self.get(value["job_id"])

    def get(self, job_id: str) -> dict:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(jobs).where(jobs.c.job_id == job_id)
            ).mappings().first()
        if row is None:
            raise KeyError(job_id)
        return _serialize(row)

    def list(self) -> list[dict]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(jobs).order_by(jobs.c.created_at.desc())
            ).mappings().all()
        return [_serialize(row) for row in rows]

    def update(self, job_id: str, **changes: object) -> dict:
        changes = {**changes, "updated_at": _now()}
        with self.engine.begin() as connection:
            existing_status = connection.scalar(
                select(jobs.c.status).where(jobs.c.job_id == job_id)
            )
            if existing_status is None:
                raise KeyError(job_id)
            result = connection.execute(
                update(jobs).where(jobs.c.job_id == job_id).values(**changes)
            )
            if result.rowcount != 1:
                raise KeyError(job_id)
            current_status = str(changes.get("status") or existing_status)
            self._event(
                connection,
                job_id,
                "status_changed" if "status" in changes else "updated",
                current_status,
                detail={
                    key: _json_safe(value)
                    for key, value in changes.items()
                    if key != "updated_at"
                },
            )
        return self.get(job_id)

    def claim_next(self, worker_id: str) -> dict | None:
        """Atomically claim one available queued job.

        PostgreSQL/EDB renders this as FOR UPDATE SKIP LOCKED, allowing
        multiple workers without claiming the same job.
        """
        now = _now()
        statement = queue_claim_statement(now)
        with self.engine.begin() as connection:
            row = connection.execute(statement).mappings().first()
            if row is None:
                return None
            attempts = int(row["attempts"]) + 1
            connection.execute(
                update(jobs)
                .where(jobs.c.job_id == row["job_id"])
                .values(
                    status="running",
                    attempts=attempts,
                    claimed_by=worker_id,
                    claimed_at=now,
                    updated_at=now,
                    error=None,
                )
            )
            self._event(
                connection,
                row["job_id"],
                "claimed",
                "running",
                worker_id=worker_id,
                detail={"attempt": attempts},
            )
        return self.get(row["job_id"])

    def succeed(self, job_id: str, worker_id: str) -> dict:
        now = _now()
        with self.engine.begin() as connection:
            result = connection.execute(
                update(jobs)
                .where(
                    jobs.c.job_id == job_id,
                    jobs.c.status == "running",
                    jobs.c.claimed_by == worker_id,
                )
                .values(
                    status="succeeded",
                    error=None,
                    claimed_by=None,
                    claimed_at=None,
                    updated_at=now,
                )
            )
            if result.rowcount != 1:
                raise JobLeaseLostError(f"worker no longer owns job: {job_id}")
            self._event(connection, job_id, "completed", "succeeded", worker_id=worker_id)
        return self.get(job_id)

    def fail(
        self,
        job_id: str,
        worker_id: str,
        error: str,
        *,
        retry_seconds: int,
    ) -> dict:
        current = self.get(job_id)
        retry = current["attempts"] < current["max_attempts"]
        status = "queued" if retry else "failed"
        now = _now()
        available_at = now + timedelta(seconds=retry_seconds) if retry else now
        with self.engine.begin() as connection:
            result = connection.execute(
                update(jobs)
                .where(
                    jobs.c.job_id == job_id,
                    jobs.c.status == "running",
                    jobs.c.claimed_by == worker_id,
                )
                .values(
                    status=status,
                    error=error,
                    available_at=available_at,
                    claimed_by=None,
                    claimed_at=None,
                    updated_at=now,
                )
            )
            if result.rowcount != 1:
                raise JobLeaseLostError(f"worker no longer owns job: {job_id}")
            self._event(
                connection,
                job_id,
                "retry_scheduled" if retry else "failed",
                status,
                worker_id=worker_id,
                detail={"error": error, "retry_seconds": retry_seconds if retry else None},
            )
        return self.get(job_id)

    def heartbeat(self, job_id: str, worker_id: str) -> bool:
        now = _now()
        with self.engine.begin() as connection:
            result = connection.execute(
                update(jobs)
                .where(
                    jobs.c.job_id == job_id,
                    jobs.c.status == "running",
                    jobs.c.claimed_by == worker_id,
                )
                .values(claimed_at=now, updated_at=now)
            )
        return result.rowcount == 1

    def recover_stale(self, stale_after_seconds: int) -> int:
        cutoff = _now() - timedelta(seconds=stale_after_seconds)
        now = _now()
        with self.engine.begin() as connection:
            stale = connection.execute(
                select(jobs.c.job_id, jobs.c.attempts, jobs.c.max_attempts).where(
                    jobs.c.status == "running",
                    jobs.c.claimed_at < cutoff,
                )
            ).mappings().all()
            for row in stale:
                job_id = row["job_id"]
                exhausted = row["attempts"] >= row["max_attempts"]
                status = "failed" if exhausted else "queued"
                connection.execute(
                    update(jobs)
                    .where(jobs.c.job_id == job_id)
                    .values(
                        status=status,
                        error=(
                            "worker lease expired; attempts exhausted"
                            if exhausted
                            else "worker lease expired; job re-queued"
                        ),
                        available_at=now,
                        claimed_by=None,
                        claimed_at=None,
                        updated_at=now,
                    )
                )
                self._event(
                    connection,
                    job_id,
                    "failed" if exhausted else "lease_recovered",
                    status,
                )
        return len(stale)

    def events(self, job_id: str) -> list[dict]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(job_events)
                .where(job_events.c.job_id == job_id)
                .order_by(job_events.c.id)
            ).mappings().all()
        return [_serialize(row) for row in rows]
