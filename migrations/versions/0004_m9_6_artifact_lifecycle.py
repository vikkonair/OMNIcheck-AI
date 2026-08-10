"""Add M9.6 Artifact Registry versioning, derivation, and event audit."""

from alembic import op
import sqlalchemy as sa


revision = "0004_m9_6"
down_revision = "0003_m9_5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "artifacts", sa.Column("artifact_version", sa.BigInteger(), nullable=False,
                               server_default="1"), schema="omnicheck"
    )
    op.alter_column(
        "artifacts", "artifact_version", server_default=None, schema="omnicheck"
    )
    op.add_column(
        "artifacts", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        schema="omnicheck",
    )
    op.add_column(
        "artifacts", sa.Column("archived_at", sa.DateTime(timezone=True)),
        schema="omnicheck",
    )
    op.add_column(
        "artifacts", sa.Column("deleted_at", sa.DateTime(timezone=True)),
        schema="omnicheck",
    )
    op.execute("UPDATE omnicheck.artifacts SET updated_at = created_at WHERE updated_at IS NULL")
    op.alter_column("artifacts", "updated_at", nullable=False, schema="omnicheck")
    op.drop_constraint("uq_artifacts_job_key", "artifacts", schema="omnicheck", type_="unique")
    op.create_unique_constraint(
        "uq_artifacts_job_type_version", "artifacts",
        ["job_id", "artifact_type", "artifact_version"], schema="omnicheck",
    )
    op.create_unique_constraint(
        "uq_artifacts_job_storage_digest", "artifacts",
        ["job_id", "storage_key", "sha256"], schema="omnicheck",
    )
    op.create_unique_constraint(
        "uq_artifacts_tenant_scope", "artifacts",
        ["artifact_id", "customer_id", "system_id", "job_id"], schema="omnicheck",
    )

    op.create_table(
        "artifact_relations",
        sa.Column("relation_id", sa.String(32), primary_key=True),
        sa.Column("customer_id", sa.String(32), nullable=False),
        sa.Column("system_id", sa.String(32), nullable=False),
        sa.Column("job_id", sa.String(32), nullable=False),
        sa.Column("parent_artifact_id", sa.String(32), nullable=False),
        sa.Column("child_artifact_id", sa.String(32), nullable=False),
        sa.Column("relation_type", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["parent_artifact_id", "customer_id", "system_id", "job_id"],
            ["omnicheck.artifacts.artifact_id", "omnicheck.artifacts.customer_id",
             "omnicheck.artifacts.system_id", "omnicheck.artifacts.job_id"],
            name="fk_artifact_relations_parent_tenant", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["child_artifact_id", "customer_id", "system_id", "job_id"],
            ["omnicheck.artifacts.artifact_id", "omnicheck.artifacts.customer_id",
             "omnicheck.artifacts.system_id", "omnicheck.artifacts.job_id"],
            name="fk_artifact_relations_child_tenant", ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "parent_artifact_id", "child_artifact_id", "relation_type",
            name="uq_artifact_relation",
        ),
        schema="omnicheck",
    )
    op.create_table(
        "artifact_events",
        sa.Column("event_id", sa.String(32), primary_key=True),
        sa.Column("artifact_id", sa.String(32), nullable=False),
        sa.Column("customer_id", sa.String(32), nullable=False),
        sa.Column("system_id", sa.String(32), nullable=False),
        sa.Column("job_id", sa.String(32), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["artifact_id", "customer_id", "system_id", "job_id"],
            ["omnicheck.artifacts.artifact_id", "omnicheck.artifacts.customer_id",
             "omnicheck.artifacts.system_id", "omnicheck.artifacts.job_id"],
            name="fk_artifact_events_artifact_tenant", ondelete="CASCADE",
        ),
        schema="omnicheck",
    )


def downgrade() -> None:
    op.drop_table("artifact_events", schema="omnicheck")
    op.drop_table("artifact_relations", schema="omnicheck")
    op.drop_constraint("uq_artifacts_tenant_scope", "artifacts", schema="omnicheck",
                       type_="unique")
    op.drop_constraint("uq_artifacts_job_storage_digest", "artifacts",
                       schema="omnicheck", type_="unique")
    op.drop_constraint("uq_artifacts_job_type_version", "artifacts",
                       schema="omnicheck", type_="unique")
    op.execute("DELETE FROM omnicheck.artifacts WHERE artifact_version > 1")
    op.create_unique_constraint(
        "uq_artifacts_job_key", "artifacts", ["job_id", "artifact_type", "storage_key"],
        schema="omnicheck",
    )
    op.drop_column("artifacts", "deleted_at", schema="omnicheck")
    op.drop_column("artifacts", "archived_at", schema="omnicheck")
    op.drop_column("artifacts", "updated_at", schema="omnicheck")
    op.drop_column("artifacts", "artifact_version", schema="omnicheck")
