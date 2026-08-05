"""Alembic environment configured only through OMNICHECK_DATABASE_URL."""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from omni_healthcheck.database import SCHEMA, metadata
import omni_healthcheck.application_data  # noqa: F401 - registers M9.4 tables
import omni_healthcheck.pipeline_persistence  # noqa: F401 - registers M9.5 tables
import omni_healthcheck.artifact_lifecycle  # noqa: F401 - registers M9.6 tables


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = os.environ.get("OMNICHECK_DATABASE_URL")
if not database_url:
    raise RuntimeError("OMNICHECK_DATABASE_URL is required for database migrations")

config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
target_metadata = metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table_schema=SCHEMA,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table_schema=SCHEMA,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
