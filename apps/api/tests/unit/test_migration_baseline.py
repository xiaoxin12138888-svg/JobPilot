import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from jobpilot_api.infrastructure.database.engine import sqlite_database_url
from jobpilot_api.infrastructure.database.models import Base


def test_model_metadata_and_migration_history_contain_only_phase_3_tables() -> None:
    config = Config("apps/api/alembic.ini")
    script = ScriptDirectory.from_config(config)

    assert set(Base.metadata.tables) == {"jobs", "applications"}
    assert len(script.get_heads()) == 1


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


def test_phase_3_migration_upgrades_and_downgrades_clean_database(tmp_path: Path) -> None:
    database_path = tmp_path / "migration" / "jobpilot.db"
    database_path.parent.mkdir(parents=True)
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlite_database_url(database_path).render_as_string())

    command.upgrade(config, "head")
    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        job_columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)").fetchall()}
        application_foreign_keys = connection.execute(
            "PRAGMA foreign_key_list(applications)"
        ).fetchall()

    assert {"jobs", "applications", "alembic_version"}.issubset(tables)
    assert "normalized_source_url" in job_columns
    assert any(
        row[2] == "jobs" and row[3] == "job_id" and row[6] == "CASCADE"
        for row in application_foreign_keys
    )

    command.downgrade(config, "base")
    with sqlite3.connect(database_path) as connection:
        remaining = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert "jobs" not in remaining
    assert "applications" not in remaining
