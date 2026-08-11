"""Add M14 Ollama Gateway request/response audit records."""

from alembic import op
import sqlalchemy as sa


revision = "0009_m14_ai_gateway"
down_revision = "0008_m10_3_sections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_gateway_requests",
        sa.Column("request_id", sa.String(32), primary_key=True),
        sa.Column("job_id", sa.String(32), nullable=False),
        sa.Column("item_id", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column("requested_by", sa.String(128), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("prompt_sha256", sa.String(64), nullable=False),
        sa.Column("response_sha256", sa.String(64)),
        sa.Column("sanitized_prompt", sa.JSON(), nullable=False),
        sa.Column("sanitized_response", sa.JSON()),
        sa.Column("usage", sa.JSON()),
        sa.Column("error_type", sa.String(64)),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["job_id"], ["omnicheck.jobs.job_id"],
            ondelete="CASCADE", name="fk_ai_gateway_requests_job",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"], ["omnicheck.section_workflow_items.item_id"],
            ondelete="CASCADE", name="fk_ai_gateway_requests_item",
        ),
        sa.CheckConstraint(
            "status IN ('started','succeeded','failed','discarded_stale')",
            name="ck_ai_gateway_requests_status",
        ),
        schema="omnicheck",
    )
    op.create_index(
        "ix_ai_gateway_requests_job_created",
        "ai_gateway_requests", ["job_id", "created_at"], schema="omnicheck",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ai_gateway_requests_job_created",
        table_name="ai_gateway_requests", schema="omnicheck",
    )
    op.drop_table("ai_gateway_requests", schema="omnicheck")
