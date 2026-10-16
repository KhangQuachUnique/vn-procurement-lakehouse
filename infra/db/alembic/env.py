import os
from collections.abc import MutableMapping
from logging.config import fileConfig
from typing import Literal

from alembic import context
from sqlalchemy import engine_from_config, pool

from vn_procurement_lakehouse.modules.ingestion.adapters.postgres.models import (
    Base,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata từ SQLAlchemy models
target_metadata = Base.metadata

# uv run --env-file .env sẽ nạp biến này
database_url = os.environ["DATABASE_URL"]

ParentNameKey = Literal[
    "schema_name",
    "table_name",
    "schema_qualified_table_name",
]


def include_name(
    name: str | None,
    type_: str,
    parent_names: MutableMapping[ParentNameKey, str | None],
) -> bool:
    if type_ == "schema":
        return name in (None, "control")

    if type_ == "table":
        qualified_name = parent_names["schema_qualified_table_name"]
        return qualified_name in target_metadata.tables

    return True


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        {"sqlalchemy.url": database_url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
