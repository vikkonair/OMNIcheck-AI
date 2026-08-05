"""Add M9.5 tenant-scoped Pipeline result persistence."""

from alembic import op
import sqlalchemy as sa

revision = "0003_m9_5"
down_revision = "0002_m9_4"
branch_labels = None
depends_on = None


def child(name: str, columns: list[sa.Column], unique_name: str) -> None:
    op.create_table(
        name,
        sa.Column("record_id", sa.String(32), primary_key=True),
        sa.Column("snapshot_id", sa.String(32), nullable=False),
        sa.Column("customer_id", sa.String(32), nullable=False),
        sa.Column("system_id", sa.String(32), nullable=False),
        sa.Column("job_id", sa.String(32), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        *columns,
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "customer_id", "system_id", "job_id"],
            ["omnicheck.pipeline_snapshots.snapshot_id", "omnicheck.pipeline_snapshots.customer_id", "omnicheck.pipeline_snapshots.system_id", "omnicheck.pipeline_snapshots.job_id"],
            name=f"fk_{name}_snapshot_tenant", ondelete="CASCADE",
        ),
        sa.UniqueConstraint("snapshot_id", "ordinal", name=unique_name),
        schema="omnicheck",
    )


def upgrade() -> None:
    op.create_table(
        "pipeline_snapshots",
        sa.Column("snapshot_id", sa.String(32), primary_key=True),
        sa.Column("customer_id", sa.String(32), nullable=False),
        sa.Column("system_id", sa.String(32), nullable=False),
        sa.Column("job_id", sa.String(32), nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("pipeline_version", sa.String(32), nullable=False),
        sa.Column("ruleset_version", sa.String(32), nullable=False),
        sa.Column("canonical_sha256", sa.String(64), nullable=False),
        sa.Column("source_snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("document_hashes", sa.JSON(), nullable=False),
        sa.Column("scope_summary", sa.JSON(), nullable=False),
        sa.Column("assessment_summary", sa.JSON(), nullable=False),
        sa.Column("coverage_summary", sa.JSON(), nullable=False),
        sa.Column("persisted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id", "customer_id", "system_id"], ["omnicheck.jobs.job_id", "omnicheck.jobs.customer_id", "omnicheck.jobs.system_id"], name="fk_pipeline_snapshots_job_tenant", ondelete="CASCADE"),
        sa.UniqueConstraint("job_id", "schema_version", "canonical_sha256", name="uq_pipeline_snapshot_identity"),
        sa.UniqueConstraint("snapshot_id", "customer_id", "system_id", "job_id", name="uq_pipeline_snapshots_tenant_scope"),
        schema="omnicheck",
    )
    child("scope_decisions", [sa.Column("evidence_sha256", sa.String(64), nullable=False), sa.Column("evidence_domain", sa.String(32), nullable=False), sa.Column("node", sa.Text()), sa.Column("node_role", sa.String(16)), sa.Column("decision", sa.String(16), nullable=False), sa.Column("reason", sa.Text(), nullable=False)], "uq_scope_decisions_snapshot_ordinal")
    child("normalized_checks", [sa.Column("check_id", sa.String(80), nullable=False), sa.Column("section_id", sa.String(24), nullable=False), sa.Column("node", sa.Text(), nullable=False), sa.Column("node_role", sa.String(16), nullable=False), sa.Column("product", sa.String(32), nullable=False), sa.Column("parser_id", sa.String(96), nullable=False), sa.Column("evidence_sha256", sa.String(64), nullable=False), sa.Column("collected_at", sa.Text())], "uq_normalized_checks_snapshot_ordinal")
    child("normalized_unparsed", [sa.Column("evidence_sha256", sa.String(64), nullable=False), sa.Column("reason", sa.Text(), nullable=False)], "uq_normalized_unparsed_snapshot_ordinal")
    child("configuration_comparisons", [sa.Column("comparison_type", sa.String(32), nullable=False), sa.Column("comparison_key", sa.Text(), nullable=False), sa.Column("status", sa.String(24))], "uq_configuration_comparisons_snapshot_ordinal")
    child("pipeline_assessments", [sa.Column("check_id", sa.String(80), nullable=False), sa.Column("section_id", sa.String(24), nullable=False), sa.Column("node", sa.Text(), nullable=False), sa.Column("status", sa.String(16), nullable=False), sa.Column("rule_id", sa.String(96), nullable=False), sa.Column("rule_version", sa.String(32), nullable=False), sa.Column("observation", sa.Text(), nullable=False), sa.Column("recommendation", sa.Text(), nullable=False)], "uq_pipeline_assessments_snapshot_ordinal")
    child("coverage_items", [sa.Column("node", sa.Text(), nullable=False), sa.Column("node_role", sa.String(16), nullable=False), sa.Column("domain", sa.String(32), nullable=False), sa.Column("check_id", sa.String(80), nullable=False), sa.Column("required", sa.Boolean(), nullable=False), sa.Column("evidence_status", sa.String(24), nullable=False), sa.Column("assessment_status", sa.String(24), nullable=False)], "uq_coverage_items_snapshot_ordinal")
    child("quality_results", [sa.Column("quality_type", sa.String(24), nullable=False), sa.Column("status", sa.String(16), nullable=False), sa.Column("delivery_allowed", sa.Boolean(), nullable=False)], "uq_quality_results_snapshot_ordinal")


def downgrade() -> None:
    for name in ("quality_results", "coverage_items", "pipeline_assessments", "configuration_comparisons", "normalized_unparsed", "normalized_checks", "scope_decisions"):
        op.drop_table(name, schema="omnicheck")
    op.drop_table("pipeline_snapshots", schema="omnicheck")
