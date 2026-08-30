from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL, make_url


def parse_postgresql_url(database_url: str) -> URL:
    url = make_url(database_url)
    if url.drivername != "postgresql+psycopg":
        raise ValueError("JobPilot persistence requires a PostgreSQL psycopg URL")
    return url


def create_database_engine(database_url: str) -> Engine:
    return create_engine(parse_postgresql_url(database_url), pool_pre_ping=True)
