from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context

from jobpilot_api.infrastructure.database.engine import create_database_engine, parse_postgresql_url
from jobpilot_api.infrastructure.database.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    configured_url = config.get_main_option("sqlalchemy.url")
    database_url = configured_url or os.environ.get("JOBPILOT_DATABASE_URL")
    if not database_url:
        raise RuntimeError("JOBPILOT_DATABASE_URL is required to run migrations")
    return database_url


def run_migrations_offline() -> None:
    database_url = _database_url()
    parse_postgresql_url(database_url)
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_database_engine(_database_url())
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
