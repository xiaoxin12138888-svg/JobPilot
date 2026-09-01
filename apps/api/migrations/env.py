from __future__ import annotations

from logging.config import fileConfig
from pathlib import Path

from alembic import context

from jobpilot_api.infrastructure.database.engine import (
    DEFAULT_DATABASE_PATH,
    create_database_engine,
    parse_sqlite_url,
    sqlite_database_url,
)
from jobpilot_api.infrastructure.database.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_path() -> Path:
    configured_url = config.get_main_option("sqlalchemy.url")
    if configured_url:
        return parse_sqlite_url(configured_url)
    return DEFAULT_DATABASE_PATH


def run_migrations_offline() -> None:
    context.configure(
        url=sqlite_database_url(_database_path()).render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_database_engine(_database_path())
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
