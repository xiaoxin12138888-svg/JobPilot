from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy.engine import make_url

API_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def database_url() -> str:
    raw_url = os.environ.get("JOBPILOT_TEST_DATABASE_URL")
    if raw_url is None:
        pytest.skip("JOBPILOT_TEST_DATABASE_URL is required for PostgreSQL integration tests")

    url = make_url(raw_url)
    if url.drivername != "postgresql+psycopg":
        pytest.fail("integration tests require the postgresql+psycopg driver")
    if not (url.database or "").endswith("_test"):
        pytest.fail("integration database name must end with _test")
    return raw_url


@pytest.fixture
def alembic_config(database_url: str) -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config
