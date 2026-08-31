from __future__ import annotations

import pytest

from jobpilot_api.infrastructure.database.engine import (
    create_database_engine,
    parse_postgresql_url,
)


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+psycopg://postgres:secret@localhost:5432/jobpilot",
        "postgresql+psycopg://postgres:secret@127.0.0.1:5432/jobpilot",
        "postgresql+psycopg://postgres:secret@[::1]:5432/jobpilot",
    ],
)
def test_database_url_accepts_only_local_postgresql_hosts(database_url: str) -> None:
    assert parse_postgresql_url(database_url).database == "jobpilot"


@pytest.mark.parametrize(
    "database_url",
    [
        "sqlite+pysqlite:///:memory:",
        "postgresql+psycopg://postgres:secret@db.example.invalid/jobpilot",
        "postgresql+psycopg://postgres:secret@192.168.1.20/jobpilot",
        "postgresql+psycopg:///jobpilot",
        "postgresql+psycopg://postgres:secret@127.0.0.1/jobpilot?host=db.example.invalid",
        "postgresql+psycopg://postgres:secret@127.0.0.1/jobpilot?hostaddr=192.168.1.20",
        "postgresql+psycopg://postgres:secret@127.0.0.1/jobpilot?service=remote-service",
    ],
)
def test_database_url_rejects_non_postgresql_or_non_loopback_hosts(
    database_url: str,
) -> None:
    with pytest.raises(ValueError, match="loopback PostgreSQL"):
        parse_postgresql_url(database_url)


def test_database_engine_hides_bound_parameters() -> None:
    engine = create_database_engine("postgresql+psycopg://postgres:password@localhost/jobpilot")

    try:
        assert engine.hide_parameters is True
    finally:
        engine.dispose()
