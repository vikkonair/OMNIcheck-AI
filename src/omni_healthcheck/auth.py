"""M11 local identity, RBAC, tenant grants, sessions, and audit records."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, Column, DateTime, ForeignKeyConstraint,
    String, Table, Text, UniqueConstraint, insert, select, update,
)
from sqlalchemy.engine import Engine, RowMapping

from omni_healthcheck.application_data import customers, systems
from omni_healthcheck.database import SCHEMA, create_database_engine, metadata


CUSTOMER_ROLES = {"engineer", "reviewer", "viewer"}
PLATFORM_ROLES = {"platform_admin"}
ROLE_PERMISSIONS = {
    "platform_admin": {"admin", "read", "create", "upload", "run", "download", "review", "audit"},
    "engineer": {"read", "create", "upload", "run", "download"},
    "reviewer": {"read", "download", "review", "audit"},
    "viewer": {"read", "download"},
}


users = Table(
    "users", metadata,
    Column("user_id", String(32), primary_key=True),
    Column("username", String(128), nullable=False, unique=True),
    Column("display_name", Text, nullable=False),
    Column("password_hash", Text, nullable=False),
    Column("platform_role", String(32)),
    Column("active", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("platform_role IS NULL OR platform_role = 'platform_admin'", name="ck_users_platform_role"),
)

customer_memberships = Table(
    "customer_memberships", metadata,
    Column("membership_id", String(32), primary_key=True),
    Column("user_id", String(32), nullable=False),
    Column("customer_id", String(32), nullable=False),
    Column("role", String(32), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(["user_id"], [f"{SCHEMA}.users.user_id"], ondelete="CASCADE", name="fk_memberships_user"),
    ForeignKeyConstraint(["customer_id"], [f"{SCHEMA}.customers.customer_id"], ondelete="CASCADE", name="fk_memberships_customer"),
    UniqueConstraint("user_id", "customer_id", name="uq_memberships_user_customer"),
    CheckConstraint("role IN ('engineer', 'reviewer', 'viewer')", name="ck_memberships_role"),
)

user_sessions = Table(
    "user_sessions", metadata,
    Column("session_id", String(32), primary_key=True),
    Column("user_id", String(32), nullable=False),
    Column("token_hash", String(64), nullable=False, unique=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True)),
    ForeignKeyConstraint(["user_id"], [f"{SCHEMA}.users.user_id"], ondelete="CASCADE", name="fk_sessions_user"),
)

audit_events = Table(
    "audit_events", metadata,
    Column("audit_id", String(32), primary_key=True),
    Column("user_id", String(32)),
    Column("username", String(128)),
    Column("customer_id", String(32)),
    Column("job_id", String(32)),
    Column("action", String(64), nullable=False),
    Column("outcome", String(16), nullable=False),
    Column("request_id", String(32), nullable=False),
    Column("client_ip", String(128)),
    Column("details", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("outcome IN ('success', 'denied', 'failed')", name="ck_audit_outcome"),
)


def _now() -> datetime:
    return datetime.now(UTC)


def _serialize(row: RowMapping) -> dict:
    value = dict(row)
    for key, item in value.items():
        if isinstance(item, datetime):
            if item.tzinfo is None:
                item = item.replace(tzinfo=UTC)
            value[key] = item.isoformat()
    value.pop("password_hash", None)
    value.pop("token_hash", None)
    return value


def hash_password(password: str, *, salt: bytes | None = None, iterations: int = 600_000) -> str:
    if len(password) < 12:
        raise ValueError("password must contain at least 12 characters")
    selected_salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), selected_salt, iterations)
    return f"pbkdf2_sha256${iterations}${selected_salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, raw_iterations, raw_salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hash_password(password, salt=bytes.fromhex(raw_salt), iterations=int(raw_iterations)).rsplit("$", 1)[1]
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


class AuthStore:
    def __init__(self, database_url: str | None = None, *, engine: Engine | None = None):
        if engine is None and database_url is None:
            raise ValueError("database_url or engine is required")
        self.engine = engine or create_database_engine(str(database_url))

    def create_schema_for_test(self) -> None:
        metadata.create_all(self.engine)

    def create_user(self, *, username: str, display_name: str, password: str,
                    platform_role: str | None = None, active: bool = True) -> dict:
        normalized = username.strip().lower()
        if not normalized or " " in normalized:
            raise ValueError("invalid username")
        if platform_role is not None and platform_role not in PLATFORM_ROLES:
            raise ValueError("invalid platform role")
        now = _now()
        record = {"user_id": uuid4().hex, "username": normalized,
                  "display_name": display_name.strip() or normalized,
                  "password_hash": hash_password(password), "platform_role": platform_role,
                  "active": active, "created_at": now, "updated_at": now}
        with self.engine.begin() as connection:
            connection.execute(insert(users).values(**record))
        return self.get_user(record["user_id"])

    def get_user(self, user_id: str) -> dict:
        with self.engine.connect() as connection:
            row = connection.execute(select(users).where(users.c.user_id == user_id)).mappings().first()
        if row is None:
            raise KeyError(user_id)
        return _serialize(row)

    def grant_customer(self, user_id: str, customer_id: str, role: str) -> dict:
        if role not in CUSTOMER_ROLES:
            raise ValueError("invalid customer role")
        now = _now()
        with self.engine.begin() as connection:
            existing = connection.execute(select(customer_memberships).where(
                customer_memberships.c.user_id == user_id,
                customer_memberships.c.customer_id == customer_id,
            )).mappings().first()
            if existing:
                connection.execute(update(customer_memberships).where(
                    customer_memberships.c.membership_id == existing["membership_id"]
                ).values(role=role))
                membership_id = existing["membership_id"]
            else:
                membership_id = uuid4().hex
                connection.execute(insert(customer_memberships).values(
                    membership_id=membership_id, user_id=user_id, customer_id=customer_id,
                    role=role, created_at=now,
                ))
            row = connection.execute(select(customer_memberships).where(
                customer_memberships.c.membership_id == membership_id
            )).mappings().one()
        return _serialize(row)

    def authenticate(self, username: str, password: str, *, ttl_hours: int = 12) -> tuple[str, dict] | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(users).where(users.c.username == username.strip().lower())).mappings().first()
        if row is None or not row["active"] or not verify_password(password, row["password_hash"]):
            return None
        token = secrets.token_urlsafe(32)
        now = _now()
        with self.engine.begin() as connection:
            connection.execute(insert(user_sessions).values(
                session_id=uuid4().hex, user_id=row["user_id"],
                token_hash=hashlib.sha256(token.encode()).hexdigest(), created_at=now,
                expires_at=now + timedelta(hours=ttl_hours), revoked_at=None,
            ))
        return token, self.identity(row["user_id"])

    def identity_for_token(self, token: str) -> dict | None:
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.engine.connect() as connection:
            row = connection.execute(
                select(user_sessions.c.user_id).where(
                    user_sessions.c.token_hash == digest,
                    user_sessions.c.revoked_at.is_(None), user_sessions.c.expires_at > _now(),
                )
            ).first()
        if not row:
            return None
        identity = self.identity(row.user_id)
        return identity if identity["active"] else None

    def identity(self, user_id: str) -> dict:
        user = self.get_user(user_id)
        with self.engine.connect() as connection:
            rows = connection.execute(select(customer_memberships).where(
                customer_memberships.c.user_id == user_id
            )).mappings().all()
        return {**user, "memberships": [_serialize(row) for row in rows]}

    def revoke(self, token: str) -> None:
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.engine.begin() as connection:
            connection.execute(update(user_sessions).where(user_sessions.c.token_hash == digest).values(revoked_at=_now()))

    @staticmethod
    def role_for(identity: dict, customer_id: str | None) -> str | None:
        if identity.get("platform_role") == "platform_admin":
            return "platform_admin"
        if customer_id is None:
            return None
        return next((item["role"] for item in identity["memberships"] if item["customer_id"] == customer_id), None)

    def allowed(self, identity: dict, permission: str, customer_id: str | None) -> bool:
        role = self.role_for(identity, customer_id)
        return permission in ROLE_PERMISSIONS.get(str(role), set())

    def context(self, identity: dict) -> dict:
        with self.engine.connect() as connection:
            statement = select(customers.c.customer_id, customers.c.name, customers.c.tenant_key).where(
                customers.c.status == "active"
            )
            if identity.get("platform_role") != "platform_admin":
                allowed_ids = [item["customer_id"] for item in identity["memberships"]]
                statement = statement.where(customers.c.customer_id.in_(allowed_ids))
            customer_rows = connection.execute(statement.order_by(customers.c.name)).mappings().all()
            customer_ids = [row["customer_id"] for row in customer_rows]
            system_rows = connection.execute(
                select(systems.c.system_id, systems.c.customer_id, systems.c.name,
                       systems.c.environment, systems.c.product)
                .where(systems.c.customer_id.in_(customer_ids), systems.c.status == "active")
                .order_by(systems.c.name)
            ).mappings().all() if customer_ids else []
        return {"identity": identity, "customers": [dict(row) for row in customer_rows],
                "systems": [dict(row) for row in system_rows]}

    def audit(self, *, action: str, outcome: str, request_id: str,
              identity: dict | None = None, customer_id: str | None = None,
              job_id: str | None = None, client_ip: str | None = None,
              details: dict | None = None) -> dict:
        record = {"audit_id": uuid4().hex, "user_id": identity.get("user_id") if identity else None,
                  "username": identity.get("username") if identity else None,
                  "customer_id": customer_id, "job_id": job_id, "action": action,
                  "outcome": outcome, "request_id": request_id, "client_ip": client_ip,
                  "details": details or {}, "created_at": _now()}
        with self.engine.begin() as connection:
            connection.execute(insert(audit_events).values(**record))
        return _serialize(record)

    def list_audit(self, identity: dict, *, customer_id: str | None = None) -> list[dict]:
        is_admin = identity.get("platform_role") == "platform_admin"
        reviewer_ids = [m["customer_id"] for m in identity["memberships"] if m["role"] == "reviewer"]
        if not is_admin and (not reviewer_ids or (customer_id and customer_id not in reviewer_ids)):
            raise PermissionError("audit access denied")
        statement = select(audit_events).order_by(audit_events.c.created_at.desc())
        if not is_admin:
            statement = statement.where(audit_events.c.customer_id.in_(reviewer_ids))
        if customer_id:
            statement = statement.where(audit_events.c.customer_id == customer_id)
        with self.engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [_serialize(row) for row in rows]
