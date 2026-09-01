import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from jobpilot_api.infrastructure.database.engine import sqlite_database_url
from jobpilot_api.infrastructure.database.models import Base


def test_model_metadata_and_migration_history_are_empty() -> None:
    config = Config("apps/api/alembic.ini")
    script = ScriptDirectory.from_config(config)

    assert set(Base.metadata.tables) == set()
    assert script.get_heads() == []


def test_alembic_connects_to_an_explicit_temporary_sqlite_database(tmp_path: Path) -> None:
    database_path = tmp_path / "migration" / "jobpilot.db"
    database_path.parent.mkdir(parents=True)
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlite_database_url(database_path).render_as_string())

    command.ensure_version(config)

    with sqlite3.connect(database_path) as connection:
        version_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'alembic_version'"
        ).fetchone()
    assert version_table == ("alembic_version",)
