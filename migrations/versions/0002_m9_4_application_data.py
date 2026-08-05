"""Add M9.4 tenant-scoped application data foundation."""

from alembic import op
import sqlalchemy as sa


revision = "0002_m9_4"
down_revision = "0001_m9_3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("tenant_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_customers_status"),
        sa.PrimaryKeyConstraint("customer_id"),
        sa.UniqueConstraint("tenant_key", name="uq_customers_tenant_key"),
        schema="omnicheck",
    )
    op.create_table(
        "systems",
        sa.Column("system_id", sa.String(length=32), nullable=False),
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("system_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("product", sa.String(length=32)),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'retired')", name="ck_systems_status"
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["omnicheck.customers.customer_id"],
            name="fk_systems_customer",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("system_id"),
        sa.UniqueConstraint("customer_id", "system_key", name="uq_systems_customer_key"),
        sa.UniqueConstraint("system_id", "customer_id", name="uq_systems_tenant_scope"),
        schema="omnicheck",
    )
    op.create_table(
        "nodes",
        sa.Column("node_id", sa.String(length=32), nullable=False),
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("system_id", sa.String(length=32), nullable=False),
        sa.Column("hostname", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("product", sa.String(length=32)),
        sa.Column("confirmed", sa.Boolean(), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('Primary', 'Standby', 'DR', 'Witness')", name="ck_nodes_role"
        ),
        sa.ForeignKeyConstraint(
            ["system_id", "customer_id"],
            ["omnicheck.systems.system_id", "omnicheck.systems.customer_id"],
            name="fk_nodes_system_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("node_id"),
        sa.UniqueConstraint("customer_id", "system_id", "hostname", name="uq_nodes_hostname"),
        sa.UniqueConstraint(
            "node_id", "customer_id", "system_id", name="uq_nodes_tenant_scope"
        ),
        schema="omnicheck",
    )
    op.create_table(
        "topology_relations",
        sa.Column("relation_id", sa.String(length=32), nullable=False),
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("system_id", sa.String(length=32), nullable=False),
        sa.Column("source_node_id", sa.String(length=32), nullable=False),
        sa.Column("target_node_id", sa.String(length=32), nullable=False),
        sa.Column("relation_type", sa.String(length=32), nullable=False),
        sa.Column("confirmation_status", sa.String(length=24), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confirmation_status IN ('confirmed', 'pending', 'rejected')",
            name="ck_topology_confirmation",
        ),
        sa.CheckConstraint(
            "source_node_id <> target_node_id", name="ck_topology_distinct_nodes"
        ),
        sa.ForeignKeyConstraint(
            ["source_node_id", "customer_id", "system_id"],
            [
                "omnicheck.nodes.node_id",
                "omnicheck.nodes.customer_id",
                "omnicheck.nodes.system_id",
            ],
            name="fk_topology_source_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["target_node_id", "customer_id", "system_id"],
            [
                "omnicheck.nodes.node_id",
                "omnicheck.nodes.customer_id",
                "omnicheck.nodes.system_id",
            ],
            name="fk_topology_target_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("relation_id"),
        sa.UniqueConstraint(
            "customer_id",
            "system_id",
            "source_node_id",
            "target_node_id",
            "relation_type",
            name="uq_topology_relation",
        ),
        schema="omnicheck",
    )

    op.add_column("jobs", sa.Column("customer_id", sa.String(length=32)), schema="omnicheck")
    op.add_column("jobs", sa.Column("system_id", sa.String(length=32)), schema="omnicheck")
    op.create_unique_constraint(
        "uq_jobs_tenant_scope",
        "jobs",
        ["job_id", "customer_id", "system_id"],
        schema="omnicheck",
    )
    op.create_foreign_key(
        "fk_jobs_customer",
        "jobs",
        "customers",
        ["customer_id"],
        ["customer_id"],
        source_schema="omnicheck",
        referent_schema="omnicheck",
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_jobs_system_tenant",
        "jobs",
        "systems",
        ["system_id", "customer_id"],
        ["system_id", "customer_id"],
        source_schema="omnicheck",
        referent_schema="omnicheck",
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_jobs_system_requires_customer",
        "jobs",
        "system_id IS NULL OR customer_id IS NOT NULL",
        schema="omnicheck",
    )

    op.create_table(
        "evidence_files",
        sa.Column("evidence_id", sa.String(length=32), nullable=False),
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("system_id", sa.String(length=32), nullable=False),
        sa.Column("job_id", sa.String(length=32), nullable=False),
        sa.Column("node_id", sa.String(length=32)),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("storage_backend", sa.String(length=32), nullable=False),
        sa.Column("storage_root_version", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("media_type", sa.String(length=128), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("file_size >= 0", name="ck_evidence_file_size"),
        sa.ForeignKeyConstraint(
            ["job_id", "customer_id", "system_id"],
            ["omnicheck.jobs.job_id", "omnicheck.jobs.customer_id", "omnicheck.jobs.system_id"],
            name="fk_evidence_job_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["node_id", "customer_id", "system_id"],
            [
                "omnicheck.nodes.node_id",
                "omnicheck.nodes.customer_id",
                "omnicheck.nodes.system_id",
            ],
            name="fk_evidence_node_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("evidence_id"),
        sa.UniqueConstraint("job_id", "storage_key", name="uq_evidence_job_storage_key"),
        schema="omnicheck",
    )
    op.create_table(
        "artifacts",
        sa.Column("artifact_id", sa.String(length=32), nullable=False),
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("system_id", sa.String(length=32), nullable=False),
        sa.Column("job_id", sa.String(length=32), nullable=False),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("storage_backend", sa.String(length=32), nullable=False),
        sa.Column("storage_root_version", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("media_type", sa.String(length=128), nullable=False),
        sa.Column("retention_until", sa.DateTime(timezone=True)),
        sa.Column("archive_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("file_size >= 0", name="ck_artifacts_file_size"),
        sa.CheckConstraint(
            "archive_status IN ('active', 'archived', 'pending_delete', 'deleted')",
            name="ck_artifacts_archive_status",
        ),
        sa.ForeignKeyConstraint(
            ["job_id", "customer_id", "system_id"],
            ["omnicheck.jobs.job_id", "omnicheck.jobs.customer_id", "omnicheck.jobs.system_id"],
            name="fk_artifacts_job_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("artifact_id"),
        sa.UniqueConstraint(
            "job_id", "artifact_type", "storage_key", name="uq_artifacts_job_key"
        ),
        schema="omnicheck",
    )


def downgrade() -> None:
    op.drop_table("artifacts", schema="omnicheck")
    op.drop_table("evidence_files", schema="omnicheck")
    op.drop_constraint("ck_jobs_system_requires_customer", "jobs", schema="omnicheck", type_="check")
    op.drop_constraint("fk_jobs_system_tenant", "jobs", schema="omnicheck", type_="foreignkey")
    op.drop_constraint("fk_jobs_customer", "jobs", schema="omnicheck", type_="foreignkey")
    op.drop_constraint("uq_jobs_tenant_scope", "jobs", schema="omnicheck", type_="unique")
    op.drop_column("jobs", "system_id", schema="omnicheck")
    op.drop_column("jobs", "customer_id", schema="omnicheck")
    op.drop_table("topology_relations", schema="omnicheck")
    op.drop_table("nodes", schema="omnicheck")
    op.drop_table("systems", schema="omnicheck")
    op.drop_table("customers", schema="omnicheck")
