"""Add M11 local identity, RBAC, tenant grants, sessions, and audit."""

from alembic import op
import sqlalchemy as sa


revision = "0005_m11"
down_revision = "0004_m9_6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("users",
        sa.Column("user_id", sa.String(32), primary_key=True),
        sa.Column("username", sa.String(128), nullable=False, unique=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("platform_role", sa.String(32)), sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("platform_role IS NULL OR platform_role = 'platform_admin'", name="ck_users_platform_role"), schema="omnicheck")
    op.create_table("customer_memberships",
        sa.Column("membership_id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), nullable=False), sa.Column("customer_id", sa.String(32), nullable=False),
        sa.Column("role", sa.String(32), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["omnicheck.users.user_id"], ondelete="CASCADE", name="fk_memberships_user"),
        sa.ForeignKeyConstraint(["customer_id"], ["omnicheck.customers.customer_id"], ondelete="CASCADE", name="fk_memberships_customer"),
        sa.UniqueConstraint("user_id", "customer_id", name="uq_memberships_user_customer"),
        sa.CheckConstraint("role IN ('engineer', 'reviewer', 'viewer')", name="ck_memberships_role"), schema="omnicheck")
    op.create_table("user_sessions",
        sa.Column("session_id", sa.String(32), primary_key=True), sa.Column("user_id", sa.String(32), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["user_id"], ["omnicheck.users.user_id"], ondelete="CASCADE", name="fk_sessions_user"), schema="omnicheck")
    op.create_table("audit_events",
        sa.Column("audit_id", sa.String(32), primary_key=True), sa.Column("user_id", sa.String(32)),
        sa.Column("username", sa.String(128)), sa.Column("customer_id", sa.String(32)), sa.Column("job_id", sa.String(32)),
        sa.Column("action", sa.String(64), nullable=False), sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("request_id", sa.String(32), nullable=False), sa.Column("client_ip", sa.String(128)),
        sa.Column("details", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("outcome IN ('success', 'denied', 'failed')", name="ck_audit_outcome"), schema="omnicheck")


def downgrade() -> None:
    op.drop_table("audit_events", schema="omnicheck")
    op.drop_table("user_sessions", schema="omnicheck")
    op.drop_table("customer_memberships", schema="omnicheck")
    op.drop_table("users", schema="omnicheck")
