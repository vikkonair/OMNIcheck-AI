"""Allow one authoritative CVE impact record per affected major release."""

from alembic import op
import sqlalchemy as sa


revision = "0011_m13_cve_major"
down_revision = "0010_m14_2_batches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cve_product_impacts",
        sa.Column("affected_major", sa.String(32), nullable=True),
        schema="omnicheck",
    )
    op.execute(
        "UPDATE omnicheck.cve_product_impacts "
        "SET affected_major = '__all__' WHERE affected_major IS NULL"
    )
    op.alter_column("cve_product_impacts", "affected_major", nullable=False, schema="omnicheck")
    op.drop_constraint("uq_cve_product_impacts_source", "cve_product_impacts", schema="omnicheck")
    op.create_unique_constraint(
        "uq_cve_product_impacts_source_major",
        "cve_product_impacts",
        ["cve_id", "product_id", "component_id", "source_id", "affected_major"],
        schema="omnicheck",
    )


def downgrade() -> None:
    op.drop_constraint("uq_cve_product_impacts_source_major", "cve_product_impacts", schema="omnicheck")
    op.create_unique_constraint(
        "uq_cve_product_impacts_source",
        "cve_product_impacts",
        ["cve_id", "product_id", "component_id", "source_id"],
        schema="omnicheck",
    )
    op.drop_column("cve_product_impacts", "affected_major", schema="omnicheck")
