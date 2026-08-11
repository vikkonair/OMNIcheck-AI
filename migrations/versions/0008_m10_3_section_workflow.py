"""Add M10.3 Section Workflow persistence and append-only revisions."""

from alembic import op
import sqlalchemy as sa


revision = "0008_m10_3_sections"
down_revision = "0007_m13_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "section_workflows",
        sa.Column("workflow_id", sa.String(32), primary_key=True),
        sa.Column("job_id", sa.String(32), nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("ruleset_version", sa.String(32), nullable=False),
        sa.Column("ai_enabled", sa.Boolean(), nullable=False),
        sa.Column("renderer_uses_ai", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["omnicheck.jobs.job_id"],
            ondelete="CASCADE", name="fk_section_workflows_job",
        ),
        sa.UniqueConstraint("job_id", name="uq_section_workflows_job"),
        schema="omnicheck",
    )
    op.create_table(
        "section_workflow_items",
        sa.Column("item_id", sa.String(32), primary_key=True),
        sa.Column("workflow_id", sa.String(32), nullable=False),
        sa.Column("section_key", sa.Text(), nullable=False),
        sa.Column("section_id", sa.String(24), nullable=False),
        sa.Column("check_id", sa.String(80), nullable=False),
        sa.Column("node", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("workflow_status", sa.String(16), nullable=False),
        sa.Column("current_revision", sa.Integer(), nullable=False),
        sa.Column("selected_source", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workflow_id"], ["omnicheck.section_workflows.workflow_id"],
            ondelete="CASCADE", name="fk_section_workflow_items_workflow",
        ),
        sa.UniqueConstraint("workflow_id", "section_key", name="uq_section_items_key"),
        sa.CheckConstraint(
            "workflow_status IN ('generated','ai_drafted','reviewed','approved')",
            name="ck_section_items_workflow_status",
        ),
        sa.CheckConstraint(
            "selected_source IN ('deterministic_template','approved')",
            name="ck_section_items_selected_source",
        ),
        schema="omnicheck",
    )
    op.create_index(
        "ix_section_items_workflow_status",
        "section_workflow_items", ["workflow_id", "workflow_status"],
        schema="omnicheck",
    )
    op.create_table(
        "section_workflow_revisions",
        sa.Column("revision_id", sa.String(32), primary_key=True),
        sa.Column("item_id", sa.String(32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id"], ["omnicheck.section_workflow_items.item_id"],
            ondelete="CASCADE", name="fk_section_revisions_item",
        ),
        sa.UniqueConstraint("item_id", "revision", name="uq_section_revisions_item_revision"),
        sa.CheckConstraint(
            "action IN ('generated','ai_drafted','reviewed','approved')",
            name="ck_section_revisions_action",
        ),
        schema="omnicheck",
    )


def downgrade() -> None:
    op.drop_table("section_workflow_revisions", schema="omnicheck")
    op.drop_index(
        "ix_section_items_workflow_status",
        table_name="section_workflow_items", schema="omnicheck",
    )
    op.drop_table("section_workflow_items", schema="omnicheck")
    op.drop_table("section_workflows", schema="omnicheck")
