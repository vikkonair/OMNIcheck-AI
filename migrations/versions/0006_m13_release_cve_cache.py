"""Add M13 official Release/CVE cache and deterministic match records."""

from alembic import op
import sqlalchemy as sa


revision = "0006_m13"
down_revision = "0005_m11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("cve_sources",
        sa.Column("source_id", sa.String(32), primary_key=True),
        sa.Column("source_key", sa.String(96), nullable=False, unique=True),
        sa.Column("source_name", sa.Text(), nullable=False), sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(24), nullable=False), sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False), sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), schema="omnicheck")
    op.create_table("cve_sync_runs",
        sa.Column("sync_run_id", sa.String(32), primary_key=True),
        sa.Column("sync_type", sa.String(16), nullable=False), sa.Column("product_id", sa.String(64)),
        sa.Column("component_id", sa.String(64)), sa.Column("status", sa.String(16), nullable=False),
        sa.Column("requested_by", sa.String(128)), sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False), sa.Column("error", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("sync_type IN ('release','cve')", name="ck_cve_sync_runs_type"),
        sa.CheckConstraint("status IN ('queued','running','succeeded','partial','failed')", name="ck_cve_sync_runs_status"), schema="omnicheck")
    op.create_table("product_releases",
        sa.Column("release_id", sa.String(32), primary_key=True), sa.Column("product_id", sa.String(64), nullable=False),
        sa.Column("product_name", sa.Text(), nullable=False), sa.Column("version", sa.String(128), nullable=False),
        sa.Column("release_family", sa.String(64)), sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.Column("source_id", sa.String(32), nullable=False), sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("raw_hash", sa.String(64), nullable=False), sa.Column("sync_run_id", sa.String(32), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False), sa.Column("active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["omnicheck.cve_sources.source_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sync_run_id"], ["omnicheck.cve_sync_runs.sync_run_id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("product_id", "version", name="uq_product_releases_product_version"), schema="omnicheck")
    op.create_index("ix_product_releases_product_fetched", "product_releases", ["product_id", "fetched_at"], schema="omnicheck")
    op.create_table("component_releases",
        sa.Column("release_id", sa.String(32), primary_key=True), sa.Column("product_id", sa.String(64), nullable=False),
        sa.Column("component_id", sa.String(64), nullable=False), sa.Column("component_name", sa.Text(), nullable=False),
        sa.Column("version", sa.String(128), nullable=False), sa.Column("release_family", sa.String(64)),
        sa.Column("released_at", sa.DateTime(timezone=True)), sa.Column("source_id", sa.String(32), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False), sa.Column("raw_hash", sa.String(64), nullable=False),
        sa.Column("sync_run_id", sa.String(32), nullable=False), sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["omnicheck.cve_sources.source_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sync_run_id"], ["omnicheck.cve_sync_runs.sync_run_id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("product_id", "component_id", "version", name="uq_component_releases_product_component_version"), schema="omnicheck")
    op.create_index("ix_component_releases_lookup", "component_releases", ["product_id", "component_id", "fetched_at"], schema="omnicheck")
    op.create_table("cve_entries",
        sa.Column("cve_id", sa.String(32), primary_key=True), sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)), sa.Column("modified_at", sa.DateTime(timezone=True)),
        sa.Column("cvss_score", sa.Numeric(4, 1)), sa.Column("severity", sa.String(24)),
        sa.Column("cvss_version", sa.String(16)), sa.Column("cvss_vector", sa.Text()),
        sa.Column("cwe", sa.JSON(), nullable=False), sa.Column("rejected", sa.Boolean(), nullable=False),
        sa.Column("raw", sa.JSON(), nullable=False), sa.Column("raw_hash", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), schema="omnicheck")
    op.create_table("cve_product_impacts",
        sa.Column("impact_id", sa.String(32), primary_key=True), sa.Column("cve_id", sa.String(32), nullable=False),
        sa.Column("product_id", sa.String(64), nullable=False), sa.Column("component_id", sa.String(64)),
        sa.Column("applicability_status", sa.String(32), nullable=False), sa.Column("affected_expression", sa.Text()),
        sa.Column("affected_from", sa.String(128)), sa.Column("affected_before", sa.String(128)),
        sa.Column("fixed_versions", sa.JSON(), nullable=False), sa.Column("vendor_assessment", sa.Text()),
        sa.Column("source_id", sa.String(32), nullable=False), sa.Column("source_priority", sa.Integer(), nullable=False),
        sa.Column("raw", sa.JSON(), nullable=False), sa.Column("sync_run_id", sa.String(32), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cve_id"], ["omnicheck.cve_entries.cve_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["omnicheck.cve_sources.source_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sync_run_id"], ["omnicheck.cve_sync_runs.sync_run_id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("cve_id", "product_id", "component_id", "source_id", name="uq_cve_product_impacts_source"),
        sa.CheckConstraint("applicability_status IN ('applicable','fixed','not_applicable','potentially_applicable','pending_confirmation')", name="ck_cve_product_impacts_status"), schema="omnicheck")
    op.create_index("ix_cve_product_impacts_product", "cve_product_impacts", ["product_id", "fetched_at"], schema="omnicheck")
    op.create_table("job_product_versions",
        sa.Column("job_product_version_id", sa.String(32), primary_key=True), sa.Column("job_id", sa.String(32), nullable=False),
        sa.Column("product_id", sa.String(64), nullable=False), sa.Column("component_id", sa.String(64)),
        sa.Column("installed_version", sa.String(128), nullable=False), sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("parser_version", sa.String(32), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["omnicheck.jobs.job_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("job_id", "product_id", "component_id", name="uq_job_product_versions_component"), schema="omnicheck")
    op.create_table("job_cve_matches",
        sa.Column("job_cve_match_id", sa.String(32), primary_key=True), sa.Column("job_id", sa.String(32), nullable=False),
        sa.Column("cve_id", sa.String(32), nullable=False), sa.Column("product_id", sa.String(64), nullable=False),
        sa.Column("component_id", sa.String(64)), sa.Column("installed_version", sa.String(128), nullable=False),
        sa.Column("match_status", sa.String(32), nullable=False), sa.Column("match_reason", sa.Text(), nullable=False),
        sa.Column("match_evidence", sa.JSON(), nullable=False), sa.Column("matcher_version", sa.String(32), nullable=False),
        sa.Column("source_snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cve_sync_run_id", sa.String(32), nullable=False), sa.Column("review_status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["omnicheck.jobs.job_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cve_id"], ["omnicheck.cve_entries.cve_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cve_sync_run_id"], ["omnicheck.cve_sync_runs.sync_run_id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("job_id", "cve_id", "product_id", "component_id", name="uq_job_cve_matches_scope"), schema="omnicheck")


def downgrade() -> None:
    op.drop_table("job_cve_matches", schema="omnicheck")
    op.drop_table("job_product_versions", schema="omnicheck")
    op.drop_index("ix_cve_product_impacts_product", table_name="cve_product_impacts", schema="omnicheck")
    op.drop_table("cve_product_impacts", schema="omnicheck")
    op.drop_table("cve_entries", schema="omnicheck")
    op.drop_index("ix_component_releases_lookup", table_name="component_releases", schema="omnicheck")
    op.drop_table("component_releases", schema="omnicheck")
    op.drop_index("ix_product_releases_product_fetched", table_name="product_releases", schema="omnicheck")
    op.drop_table("product_releases", schema="omnicheck")
    op.drop_table("cve_sync_runs", schema="omnicheck")
    op.drop_table("cve_sources", schema="omnicheck")
