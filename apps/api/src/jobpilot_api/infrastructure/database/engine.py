from __future__ import annotations

from ipaddress import ip_address

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL, make_url


def parse_postgresql_url(database_url: str) -> URL:
    url = make_url(database_url)
    host = url.host
    if (
        url.drivername != "postgresql+psycopg"
        or host is None
        or not _is_loopback_host(host)
        or url.query
    ):
        raise ValueError("JobPilot persistence requires a loopback PostgreSQL psycopg URL")
    return url


def _is_loopback_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def create_database_engine(database_url: str) -> Engine:
    return create_engine(
        parse_postgresql_url(database_url),
        hide_parameters=True,
        pool_pre_ping=True,
    )
