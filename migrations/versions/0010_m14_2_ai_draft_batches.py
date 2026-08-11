"""Add durable controlled batches for M14.2 Section AI drafts."""

from alembic import op
import sqlalchemy as sa


revision = "0010_m14_2_batches"
down_revision = "0009_m14_ai_gateway"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_draft_batches",
        sa.Column("batch_id", sa.String(32), primary_key=True),
        sa.Column("job_id", sa.String(32), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("completed_items", sa.Integer(), nullable=False),
        sa.Column("succeeded_items", sa.Integer(), nullable=False),
        sa.Column("fallback_items", sa.Integer(), nullable=False),
        sa.Column("conflict_items", sa.Integer(), nullable=False),
        sa.Column("claimed_by", sa.Text()),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["job_id"], ["omnicheck.jobs.job_id"], ondelete="CASCADE",
            name="fk_ai_draft_batches_job",
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','partial','failed')",
            name="ck_ai_draft_batches_status",
        ),
        schema="omnicheck",
    )
    op.create_index(
        "ix_ai_draft_batches_queue", "ai_draft_batches",
        ["status", "created_at"], schema="omnicheck",
    )
    op.create_table(
        "ai_draft_batch_items",
        sa.Column("batch_item_id", sa.String(32), primary_key=True),
        sa.Column("batch_id", sa.String(32), nullable=False),
        sa.Column("item_id", sa.String(32), nullable=False),
        sa.Column("expected_revision", sa.Integer(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("request_id", sa.String(32)),
        sa.Column("error", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["batch_id"], ["omnicheck.ai_draft_batches.batch_id"],
            ondelete="CASCADE", name="fk_ai_draft_batch_items_batch",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"], ["omnicheck.section_workflow_items.item_id"],
            ondelete="CASCADE", name="fk_ai_draft_batch_items_section",
        ),
        sa.UniqueConstraint("batch_id", "item_id", name="uq_ai_batch_item"),
        sa.CheckConstraint(
            "status IN ('queued','running','ai_drafted','fallback','conflict')",
            name="ck_ai_draft_batch_items_status",
        ),
        schema="omnicheck",
    )


def downgrade() -> None:
    op.drop_table("ai_draft_batch_items", schema="omnicheck")
    op.drop_index(
        "ix_ai_draft_batches_queue", table_name="ai_draft_batches",
        schema="omnicheck",
    )
    op.drop_table("ai_draft_batches", schema="omnicheck")
