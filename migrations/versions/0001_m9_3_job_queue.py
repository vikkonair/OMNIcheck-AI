"""Create M9.3 durable job metadata and event tables."""

from alembic import op
import sqlalchemy as sa


revision = "0001_m9_3"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("job_id", sa.String(length=32), nullable=False),
        sa.Column("customer", sa.Text(), nullable=False),
        sa.Column("system_name", sa.Text()),
        sa.Column("period", sa.Text(), nullable=False),
        sa.Column("product", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("input_files", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("claimed_by", sa.Text()),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("job_id"),
        schema="omnicheck",
    )
    op.create_index(
        "ix_jobs_status",
        "jobs",
        ["status"],
        schema="omnicheck",
    )
    op.create_table(
        "job_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("worker_id", sa.Text()),
        sa.Column("detail", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["omnicheck.jobs.job_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="omnicheck",
    )
    op.create_index(
        "ix_job_events_job_id",
        "job_events",
        ["job_id"],
        schema="omnicheck",
    )


def downgrade() -> None:
    op.drop_index("ix_job_events_job_id", table_name="job_events", schema="omnicheck")
    op.drop_table("job_events", schema="omnicheck")
    op.drop_index("ix_jobs_status", table_name="jobs", schema="omnicheck")
    op.drop_table("jobs", schema="omnicheck")
