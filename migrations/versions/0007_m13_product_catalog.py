"""Add the DB-backed M13 product/component catalog and major-version channels."""

from alembic import op
import sqlalchemy as sa


revision = "0007_m13_catalog"
down_revision = "0006_m13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_products",
        sa.Column("product_id", sa.String(64), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("edition", sa.String(24), nullable=False),
        sa.Column("release_source", sa.Text(), nullable=False),
        sa.Column("cve_keyword", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "edition IN ('open_source','commercial','mixed')",
            name="ck_knowledge_products_edition",
        ),
        schema="omnicheck",
    )
    op.create_table(
        "knowledge_components",
        sa.Column("component_id", sa.String(64), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema="omnicheck",
    )
    op.create_table(
        "knowledge_product_components",
        sa.Column("product_id", sa.String(64), nullable=False),
        sa.Column("component_id", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("sync_supported", sa.Boolean(), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.ForeignKeyConstraint(
            ["product_id"], ["omnicheck.knowledge_products.product_id"],
            ondelete="CASCADE", name="fk_knowledge_product_components_product",
        ),
        sa.ForeignKeyConstraint(
            ["component_id"], ["omnicheck.knowledge_components.component_id"],
            ondelete="RESTRICT", name="fk_knowledge_product_components_component",
        ),
        sa.PrimaryKeyConstraint("product_id", "component_id"),
        sa.CheckConstraint(
            "kind IN ('primary','tool','bundled')",
            name="ck_knowledge_product_components_kind",
        ),
        schema="omnicheck",
    )
    op.create_table(
        "knowledge_release_channels",
        sa.Column("channel_id", sa.String(64), primary_key=True),
        sa.Column("product_id", sa.String(64), nullable=False),
        sa.Column("component_id", sa.String(64), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("major_version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"], ["omnicheck.knowledge_products.product_id"],
            ondelete="CASCADE", name="fk_knowledge_release_channels_product",
        ),
        sa.ForeignKeyConstraint(
            ["component_id"], ["omnicheck.knowledge_components.component_id"],
            ondelete="RESTRICT", name="fk_knowledge_release_channels_component",
        ),
        sa.UniqueConstraint(
            "product_id", "component_id", "major_version",
            name="uq_knowledge_release_channel",
        ),
        sa.CheckConstraint(
            "status IN ('active','maintenance','eol','unknown')",
            name="ck_knowledge_release_channels_status",
        ),
        schema="omnicheck",
    )
    op.create_table(
        "knowledge_product_aliases",
        sa.Column("alias_id", sa.String(32), primary_key=True),
        sa.Column("product_id", sa.String(64), nullable=False),
        sa.Column("alias", sa.String(128), nullable=False),
        sa.Column("scope", sa.String(24), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"], ["omnicheck.knowledge_products.product_id"],
            ondelete="CASCADE", name="fk_knowledge_product_aliases_product",
        ),
        sa.UniqueConstraint("alias", "scope", name="uq_knowledge_product_alias_scope"),
        schema="omnicheck",
    )


def downgrade() -> None:
    op.drop_table("knowledge_product_aliases", schema="omnicheck")
    op.drop_table("knowledge_release_channels", schema="omnicheck")
    op.drop_table("knowledge_product_components", schema="omnicheck")
    op.drop_table("knowledge_components", schema="omnicheck")
    op.drop_table("knowledge_products", schema="omnicheck")
