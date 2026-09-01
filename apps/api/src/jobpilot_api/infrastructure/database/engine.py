from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import URL, make_url

REPOSITORY_ROOT = Path(__file__).resolve().parents[6]
DEFAULT_DATABASE_PATH = REPOSITORY_ROOT / "runtime-data" / "jobpilot.db"
SQLITE_BUSY_TIMEOUT_MILLISECONDS = 5_000


def sqlite_database_url(database_path: Path) -> URL:
    return URL.create(
        "sqlite+pysqlite",
        database=str(database_path.expanduser().resolve()),
    )


def parse_sqlite_url(database_url: str) -> Path:
    url = make_url(database_url)
    if (
        url.drivername != "sqlite+pysqlite"
        or url.database in (None, "", ":memory:")
        or url.username is not None
        or url.password is not None
        or url.host is not None
        or url.port is not None
        or url.query
    ):
        raise ValueError("JobPilot persistence requires an absolute SQLite pysqlite file URL")

    database_path = Path(url.database)
    if not database_path.is_absolute():
        raise ValueError("JobPilot persistence requires an absolute SQLite pysqlite file URL")
    return database_path.resolve()


def _configure_sqlite_connection(
    dbapi_connection: sqlite3.Connection,
    _connection_record: object,
) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MILLISECONDS}")
    finally:
        cursor.close()


def create_database_engine(database_path: Path = DEFAULT_DATABASE_PATH) -> Engine:
    resolved_path = database_path.expanduser().resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        sqlite_database_url(resolved_path),
        connect_args={"timeout": SQLITE_BUSY_TIMEOUT_MILLISECONDS / 1_000},
        hide_parameters=True,
    )
    event.listen(engine, "connect", _configure_sqlite_connection)
    return engine


def initialize_database(database_path: Path = DEFAULT_DATABASE_PATH) -> Path:
    resolved_path = database_path.expanduser().resolve()
    engine = create_database_engine(resolved_path)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("SELECT 1")
    finally:
        engine.dispose()
    return resolved_path
