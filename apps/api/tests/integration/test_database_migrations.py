from __future__ import annotations

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from jobpilot_api.infrastructure.database.engine import create_database_engine
from jobpilot_api.infrastructure.database.models import Base

AUTH_TABLES = {"users", "identities", "web_sessions", "login_transactions"}


def test_model_metadata_and_migration_history_are_empty() -> None:
    config = Config("apps/api/alembic.ini")
    script = ScriptDirectory.from_config(config)

    assert set(Base.metadata.tables) == set()
    assert script.get_heads() == []


def test_empty_migrations_leave_no_auth_tables(
    alembic_config: Config,
    database_url: str,
) -> None:
    command.upgrade(alembic_config, "head")
    engine = create_database_engine(database_url)
    try:
        assert AUTH_TABLES.isdisjoint(inspect(engine).get_table_names())
        command.check(alembic_config)
    finally:
        engine.dispose()
