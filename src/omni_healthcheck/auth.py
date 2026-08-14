"""M11 local identity, RBAC, tenant isolation, and audit primitives.

Authentication is deliberately optional during the internal single-user phase.
When enabled, opaque sessions are stored only as SHA-256 hashes and every
customer-scoped lookup is enforced server-side.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, JSON, String, Table, Text, insert, select
from sqlalchemy.engine import Engine

from omni_healthcheck.application_data import customers, systems
from omni_healthcheck.database import SCHEMA, metadata


CURRENT_PRINCIPAL: ContextVar["Principal | None"] = ContextVar("omnicheck_principal", default=None)
MEMBERSHIP_ROLES = {"engineer", "reviewer", "viewer"}
ROLE_RANK = {"viewer": 1, "reviewer": 2, "engineer": 3, "platform_admin": 4}

users = Table(
    "users", metadata,
    Column("user_id", String(32), primary_key=True),
    Column("username", String(128), nullable=False, unique=True),
    Column("display_name", Text, nullable=False),
    Column("password_hash", Text, nullable=False),
    Column("platform_role", String(32)), Column("active", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("platform_role IS NULL OR platform_role = 'platform_admin'", name="ck_users_platform_role"),
)
customer_memberships = Table(
    "customer_memberships", metadata,
    Column("membership_id", String(32), primary_key=True),
    Column("user_id", String(32), ForeignKey(f"{SCHEMA}.users.user_id", ondelete="CASCADE"), nullable=False),
    Column("customer_id", String(32), ForeignKey(f"{SCHEMA}.customers.customer_id", ondelete="CASCADE"), nullable=False),
    Column("role", String(32), nullable=False), Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("role IN ('engineer', 'reviewer', 'viewer')", name="ck_memberships_role"),
)
user_sessions = Table(
    "user_sessions", metadata,
    Column("session_id", String(32), primary_key=True),
    Column("user_id", String(32), ForeignKey(f"{SCHEMA}.users.user_id", ondelete="CASCADE"), nullable=False),
    Column("token_hash", String(64), nullable=False, unique=True),
    Column("created_at", DateTime(timezone=True), nullable=False), Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True)),
)
audit_events = Table(
    "audit_events", metadata,
    Column("audit_id", String(32), primary_key=True), Column("user_id", String(32)), Column("username", String(128)),
    Column("customer_id", String(32)), Column("job_id", String(32)), Column("action", String(64), nullable=False),
    Column("outcome", String(16), nullable=False), Column("request_id", String(32), nullable=False),
    Column("client_ip", String(128)), Column("details", JSON, nullable=False), Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("outcome IN ('success', 'denied', 'failed')", name="ck_audit_outcome"),
)


def _now() -> datetime:
    return datetime.now(UTC)


def _id() -> str:
    return uuid4().hex


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("password must be at least 12 characters")
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt$16384$8$1${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$")
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


@dataclass(frozen=True)
class Principal:
    user_id: str
    username: str
    display_name: str
    platform_role: str | None

    @property
    def is_admin(self) -> bool:
        return self.platform_role == "platform_admin"


class AuthStore:
    def __init__(self, *, engine: Engine, enabled: bool | None = None):
        self.engine = engine
        self.enabled = enabled if enabled is not None else os.environ.get("OMNICHECK_AUTH_ENABLED", "false").lower() == "true"
        self.session_hours = max(1, int(os.environ.get("OMNICHECK_AUTH_SESSION_HOURS", "8")))

    def user_count(self) -> int:
        with self.engine.connect() as connection:
            return len(connection.execute(select(users.c.user_id)).all())

    def create_user(self, *, username: str, display_name: str, password: str, platform_admin: bool = False) -> dict[str, Any]:
        username = username.strip().lower()
        if not username or len(username) > 128 or any(character.isspace() for character in username):
            raise ValueError("username must be a non-empty identifier without spaces")
        if not display_name.strip():
            raise ValueError("display_name is required")
        now = _now()
        record = {"user_id": _id(), "username": username, "display_name": display_name.strip(), "password_hash": hash_password(password), "platform_role": "platform_admin" if platform_admin else None, "active": True, "created_at": now, "updated_at": now}
        with self.engine.begin() as connection:
            connection.execute(insert(users).values(**record))
        return self._user(record["user_id"])

    def _user(self, user_id: str) -> dict[str, Any]:
        with self.engine.connect() as connection:
            row = connection.execute(select(users).where(users.c.user_id == user_id)).mappings().first()
        if row is None:
            raise KeyError(user_id)
        return dict(row)

    def authenticate(self, username: str, password: str) -> Principal | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(users).where(users.c.username == username.strip().lower(), users.c.active.is_(True))).mappings().first()
        if row is None or not verify_password(password, str(row["password_hash"])):
            return None
        return Principal(str(row["user_id"]), str(row["username"]), str(row["display_name"]), row["platform_role"])

    def issue_session(self, principal: Principal) -> tuple[str, str]:
        token, csrf, now = secrets.token_urlsafe(32), secrets.token_urlsafe(24), _now()
        with self.engine.begin() as connection:
            connection.execute(insert(user_sessions).values(session_id=_id(), user_id=principal.user_id, token_hash=_token_hash(token), created_at=now, expires_at=now + timedelta(hours=self.session_hours), revoked_at=None))
        return token, csrf

    def principal_for_token(self, token: str | None) -> Principal | None:
        if not token:
            return None
        with self.engine.connect() as connection:
            row = connection.execute(select(users).join(user_sessions, users.c.user_id == user_sessions.c.user_id).where(user_sessions.c.token_hash == _token_hash(token), user_sessions.c.revoked_at.is_(None), user_sessions.c.expires_at > _now(), users.c.active.is_(True))).mappings().first()
        return None if row is None else Principal(str(row["user_id"]), str(row["username"]), str(row["display_name"]), row["platform_role"])

    def revoke(self, token: str | None) -> None:
        if not token:
            return
        from sqlalchemy import update
        with self.engine.begin() as connection:
            connection.execute(update(user_sessions).where(user_sessions.c.token_hash == _token_hash(token), user_sessions.c.revoked_at.is_(None)).values(revoked_at=_now()))

    def grant(self, *, user_id: str, customer_id: str, role: str) -> None:
        if role not in MEMBERSHIP_ROLES:
            raise ValueError("invalid membership role")
        with self.engine.begin() as connection:
            connection.execute(insert(customer_memberships).values(membership_id=_id(), user_id=user_id, customer_id=customer_id, role=role, created_at=_now()))

    def customer_role(self, principal: Principal, customer_id: str) -> str | None:
        if principal.is_admin:
            return "platform_admin"
        with self.engine.connect() as connection:
            row = connection.execute(select(customer_memberships.c.role).where(customer_memberships.c.user_id == principal.user_id, customer_memberships.c.customer_id == customer_id)).first()
        return str(row[0]) if row else None

    def require_customer(self, principal: Principal, customer_id: str, minimum: str = "viewer") -> None:
        role = self.customer_role(principal, customer_id)
        if role is None or ROLE_RANK[role] < ROLE_RANK[minimum]:
            raise PermissionError("customer access is not authorized")

    def require_job(self, principal: Principal, job: dict[str, Any], minimum: str = "viewer") -> None:
        customer_id = job.get("customer_id")
        if not customer_id:
            if not principal.is_admin:
                raise PermissionError("legacy unscoped jobs require platform administrator")
            return
        self.require_customer(principal, str(customer_id), minimum)

    def scope(self, principal: Principal) -> list[dict[str, Any]]:
        statement = select(customers.c.customer_id, customers.c.name, customers.c.tenant_key, systems.c.system_id, systems.c.name.label("system_name"), systems.c.product).join(systems, systems.c.customer_id == customers.c.customer_id).where(customers.c.status == "active", systems.c.status == "active")
        if not principal.is_admin:
            statement = statement.join(customer_memberships, customer_memberships.c.customer_id == customers.c.customer_id).where(customer_memberships.c.user_id == principal.user_id)
        with self.engine.connect() as connection:
            return [dict(row) for row in connection.execute(statement.order_by(customers.c.name, systems.c.name)).mappings().all()]

    def resolve_scope(self, principal: Principal, *, customer: str, system_name: str | None) -> tuple[str, str]:
        if not system_name:
            raise ValueError("authenticated jobs require system_name")
        matches = [entry for entry in self.scope(principal) if entry["name"] == customer and entry["system_name"] == system_name]
        if len(matches) != 1:
            raise PermissionError("customer or system is not authorized")
        return str(matches[0]["customer_id"]), str(matches[0]["system_id"])

    def audit(self, *, principal: Principal | None, action: str, outcome: str, request_id: str, customer_id: str | None = None, job_id: str | None = None, client_ip: str | None = None, details: dict[str, Any] | None = None) -> None:
        with self.engine.begin() as connection:
            connection.execute(insert(audit_events).values(audit_id=_id(), user_id=principal.user_id if principal else None, username=principal.username if principal else None, customer_id=customer_id, job_id=job_id, action=action, outcome=outcome, request_id=request_id, client_ip=client_ip, details=details or {}, created_at=_now()))
