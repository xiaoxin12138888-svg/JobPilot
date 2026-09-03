from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from jobpilot_api.infrastructure.database.engine import (
    DEFAULT_DATABASE_PATH,
    SQLITE_BUSY_TIMEOUT_MILLISECONDS,
    create_database_engine,
    sqlite_database_url,
    upgrade_database,
)


def test_default_database_path_is_the_ignored_repository_runtime_data_file() -> None:
    repository_root = Path(__file__).resolve().parents[4]

    assert DEFAULT_DATABASE_PATH == repository_root / "runtime-data" / "jobpilot.db"
    assert (
        "runtime-data/" in (repository_root / ".gitignore").read_text(encoding="utf-8").splitlines()
    )


def test_upgrade_creates_the_parent_directory_and_database(tmp_path: Path) -> None:
    database_path = tmp_path / "nested" / "runtime-data" / "jobpilot.db"

    upgraded_path = upgrade_database(database_path)

    assert upgraded_path == database_path.resolve()
    assert database_path.is_file()


def test_second_upgrade_reuses_the_database_without_overwriting_data(tmp_path: Path) -> None:
    database_path = tmp_path / "runtime-data" / "jobpilot.db"
    upgrade_database(database_path)
    first_engine = create_database_engine(database_path)
    try:
        with first_engine.begin() as connection:
            connection.execute(text("CREATE TABLE restart_marker (value TEXT NOT NULL)"))
            connection.execute(
                text("INSERT INTO restart_marker (value) VALUES (:value)"),
                {"value": "preserved"},
            )
    finally:
        first_engine.dispose()

    upgrade_database(database_path)
    second_engine = create_database_engine(database_path)
    try:
        with second_engine.connect() as connection:
            value = connection.scalar(text("SELECT value FROM restart_marker"))
    finally:
        second_engine.dispose()

    assert value == "preserved"


def test_every_sqlite_connection_enables_foreign_keys_and_busy_timeout(tmp_path: Path) -> None:
    database_path = tmp_path / "jobpilot.db"
    engine = create_database_engine(database_path)
    try:
        with engine.begin() as connection:
            foreign_keys = connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one()
            busy_timeout = connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one()
            connection.exec_driver_sql("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
            connection.exec_driver_sql(
                "CREATE TABLE child (parent_id INTEGER REFERENCES parent(id))"
            )

        with engine.begin() as connection:
            try:
                connection.exec_driver_sql("INSERT INTO child (parent_id) VALUES (999)")
            except IntegrityError:
                pass
            else:
                raise AssertionError("SQLite foreign key enforcement was not enabled")
    finally:
        engine.dispose()

    assert foreign_keys == 1
    assert busy_timeout == SQLITE_BUSY_TIMEOUT_MILLISECONDS


def test_database_engine_hides_bound_parameters_and_keeps_default_journal_mode(
    tmp_path: Path,
) -> None:
    engine = create_database_engine(tmp_path / "jobpilot.db")
    try:
        with engine.connect() as connection:
            journal_mode = connection.exec_driver_sql("PRAGMA journal_mode").scalar_one()
        assert engine.hide_parameters is True
        assert journal_mode == "delete"
    finally:
        engine.dispose()


def test_sqlite_database_url_uses_an_absolute_file_path(tmp_path: Path) -> None:
    database_path = tmp_path / "jobpilot.db"

    assert sqlite_database_url(database_path).database == str(database_path.resolve())
